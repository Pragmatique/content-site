# src/payment/services.py
from web3 import Web3
from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import requests
from uuid import uuid4
import time  # Для backoff в retry
import logging
from web3.middleware import geth_poa_middleware

from payment.models import Payment, Discount
from payment.schemas import PaymentResponse, DiscountCreate, DiscountResponse, PaymentCreateResponse
from subscription.models import Subscription
from config import settings

logger = logging.getLogger(__name__)  # Логгер для детализации ошибок и параметров

class PaymentService:
    def __init__(self):
        self.tron_wallet_address = settings.TRON_WALLET_ADDRESS
        self.bsc = Web3(Web3.HTTPProvider(settings.BSC_FULL_NODE))
        self.bsc.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.bsc_wallet_address = settings.BSC_WALLET_ADDRESS
        self.usdt_trc20_address = settings.USDT_TRC20_ADDRESS
        self.usdt_bep20_address = settings.USDT_BEP20_ADDRESS
        self.usdt_bep20_abi = [
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
                    {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
                    {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"}
                ],
                "name": "Transfer",
                "type": "event"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
                "payable": False,
                "stateMutability": "view",
                "type": "function"
            }
        ]
        self.usdt_bep20_contract = self.bsc.eth.contract(
            address=self.usdt_bep20_address,
            abi=self.usdt_bep20_abi
        )
        # Динамически получаем decimals для USDT BEP20
        try:
            self.usdt_bep20_decimals = self.usdt_bep20_contract.functions.decimals().call()
            logger.info(f"USDT BEP20 decimals: {self.usdt_bep20_decimals}")
        except Exception as e:
            logger.error(f"Error getting USDT BEP20 decimals: {str(e)}")
            self.usdt_bep20_decimals = settings.USDT_BEP20_DECIMALS  # Fallback из config

    @staticmethod
    def generate_unique_amount(final_price: float, db: Session) -> float:
        candidates = [
            final_price,
            final_price - 0.01, final_price + 0.01,
            final_price - 0.02, final_price + 0.02,
        ]
        for amount in candidates:
            if amount <= 0:
                continue
            int_amount = int(amount * 100)
            exists = db.query(Payment).filter(
                Payment.amount == int_amount,
                Payment.status == "pending",
                Payment.expiration_time > datetime.now(timezone.utc)
            ).first()
            if not exists:
                return amount
        raise HTTPException(status_code=400, detail="No available unique amount. Try again later.")

    def create_payment(self, user_id: int, purpose: str, level: Optional[str], amount: float, currency: str, db: Session) -> PaymentCreateResponse:
        if currency == "usdttrc20":
            address = self.tron_wallet_address
        elif currency == "usdtbep20":
            address = self.bsc_wallet_address
        else:
            raise HTTPException(status_code=400, detail="Unsupported currency")

        now_utc = datetime.now(timezone.utc)
        expiry_utc = now_utc + timedelta(minutes=30)
        payment = Payment(
            user_id=user_id,
            purpose=purpose,
            level=level if purpose == "subscription" else None,
            payment_method="crypto",
            client_payment_id=f"pay_{uuid4().hex[:12]}",
            amount=int(amount * 100),
            currency=currency,
            status="pending",
            expiration_time=expiry_utc.replace(tzinfo=None),  # Save naive for DB
            created_at=now_utc.replace(tzinfo=None)  # Save naive for DB
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        return PaymentCreateResponse(
            client_payment_id=payment.client_payment_id,
            payment_url=address,
            amount=amount,
            final_amount=amount,
            discount_info="",
            expires_at=payment.expiration_time,
            currency=currency
        )

    def check_payment(self, payment: Payment, db: Session) -> bool:
        amount_in_usd = payment.amount / 100.0
        created_at_utc = payment.created_at.replace(tzinfo=timezone.utc)
        expiration_utc = payment.expiration_time.replace(tzinfo=timezone.utc)
        min_ts = int(created_at_utc.timestamp() * 1000)
        max_ts = int(expiration_utc.timestamp() * 1000)
        current_time = datetime.now(timezone.utc)

        min_dt = datetime.fromtimestamp(min_ts / 1000, tz=timezone.utc)
        max_dt = datetime.fromtimestamp(max_ts / 1000, tz=timezone.utc)

        logger.info(f"Checking payment {payment.client_payment_id}: currency={payment.currency}, expected_amount={amount_in_usd}, created_at={created_at_utc.isoformat()} (UTC), expiration_time={expiration_utc.isoformat()} (UTC), current_time={current_time.isoformat()} (UTC), min_ts={min_ts}, max_ts={max_ts}, min_dt={min_dt.isoformat()} (UTC), max_dt={max_dt.isoformat()} (UTC)")

        if payment.currency == "usdttrc20":
            url = f"{settings.TRON_FULL_NODE}/v1/accounts/{self.tron_wallet_address}/transactions/trc20"
            params = {
                "contract_address": self.usdt_trc20_address,
                "min_timestamp": min_ts,
                "max_timestamp": max_ts
            }
            logger.info(f"TRON API call: url={url}, params={params}")
            try:
                response = requests.get(url, params=params, timeout=10)
                logger.info(f"TRON API response status: {response.status_code}")
                if response.status_code != 200:
                    logger.error(f"TRON API non-200 status: {response.status_code}, text={response.text}")
                    return False
                data = response.json().get("data", [])
                logger.info(f"Found {len(data)} transactions in TRON response")
                if not data:
                    logger.info("No transactions found in API response")
                logger.info("Matching only by to and amount, trusting API filter")
                for tx in data:
                    ts = tx.get("timestamp", 0)
                    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat() if ts else "N/A"
                    calculated_value = float(tx.get("value", 0)) / 10 ** 6
                    logger.info(f"Tx ID: {tx.get('transaction_id')}, To: {tx.get('to')}, Raw Value: {tx.get('value')}, Calculated Value: {calculated_value}, Timestamp: {ts} ({dt} UTC), Type: {tx.get('type')}")
                    if ts != 0 and not (min_ts <= ts <= max_ts):
                        logger.info(f"API returned tx with unexpected ts {ts} ({dt} UTC) outside requested range {min_ts}-{max_ts} ({min_dt.isoformat()}-{max_dt.isoformat()} UTC)")
                        continue
                    if (tx["to"] == self.tron_wallet_address and
                            calculated_value == amount_in_usd):
                        payment.transaction_id = tx["transaction_id"]
                        db.commit()
                        logger.info(f"Matched tx {tx['transaction_id']} with amount {calculated_value}")
                        return True
                    elif calculated_value != amount_in_usd:
                        logger.info(f"Mismatched amount in tx {tx.get('transaction_id')}: calculated {calculated_value} != expected {amount_in_usd}")
            except Exception as e:
                logger.error(f"TRON API error for payment {payment.client_payment_id}: {str(e)}")
        elif payment.currency == "usdtbep20":
            latest_block = self.bsc.eth.block_number
            time_diff_sec = (max_ts - min_ts) / 1000
            blocks_to_scan = int(time_diff_sec // 3) + 1000
            from_block = max(0, latest_block - blocks_to_scan)

            try:
                latest_ts = self.bsc.eth.get_block(latest_block)['timestamp'] * 1000
                from_ts = self.bsc.eth.get_block(from_block)['timestamp'] * 1000
                logger.info(f"Scan range ts: from_ts={from_ts} to latest_ts={latest_ts}")
            except Exception as e:
                logger.error(f"Error getting block ts: {str(e)}")

            logger.info(f"BSC scan for payment {payment.client_payment_id}: from_block={from_block}, to_block={latest_block}, blocks_to_scan={blocks_to_scan}")

            chunk_size = 50
            current_block = from_block
            while current_block < latest_block:
                chunk_end = min(current_block + chunk_size, latest_block)
                for attempt in range(3):
                    time.sleep(0.5)
                    try:
                        transfer_events = self.usdt_bep20_contract.events.Transfer.get_logs(
                            fromBlock=current_block,
                            toBlock=chunk_end,
                            argument_filters={"to": self.bsc_wallet_address}
                        )
                        logger.info(f"Found {len(transfer_events)} transfer events in chunk {current_block}-{chunk_end}, attempt {attempt + 1}")
                        for event in transfer_events:
                            try:
                                block_ts = self.bsc.eth.get_block(event.blockNumber)['timestamp'] * 1000
                            except Exception as ts_e:
                                logger.error(f"Error getting block_ts for block {event.blockNumber}: {str(ts_e)}")
                                continue
                            amount_transferred = event["args"]["value"] / 10 ** self.usdt_bep20_decimals  # Используем динамические decimals
                            logger.info(f"Event tx {event['transactionHash'].hex()}, from {event['args']['from']}, to {event['args']['to']}, raw_value {event['args']['value']}, amount_transferred {amount_transferred}, block {event.blockNumber}, block_ts {block_ts}")
                            if min_ts <= block_ts <= max_ts:
                                if amount_transferred == amount_in_usd:
                                    payment.transaction_id = event["transactionHash"].hex()
                                    db.commit()
                                    logger.info(f"Payment {payment.client_payment_id} matched tx {payment.transaction_id}")
                                    return True
                                else:
                                    logger.info(f"Mismatched amount in tx {event['transactionHash'].hex()}: transferred {amount_transferred} != expected {amount_in_usd}")
                            else:
                                logger.info(f"Event outside range: tx {event['transactionHash'].hex()}, block_ts {block_ts} not in {min_ts}-{max_ts}")
                        break
                    except Exception as e:
                        logger.error(f"BSC error for payment {payment.client_payment_id} in chunk {current_block}-{chunk_end}, attempt {attempt + 1}: {str(e)}")
                        if attempt < 2:
                            sleep_time = 2 ** attempt
                            logger.info(f"Retrying chunk after {sleep_time} sec backoff")
                            time.sleep(sleep_time)
                        else:
                            return False
                current_block = chunk_end + 1
            logger.info(f"No matching events for payment {payment.client_payment_id} after scanning all chunks")
        return False

    def confirm_payment(self, payment: Payment, db: Session):
        """Confirm logic after blockchain success."""
        if payment.purpose != "subscription":
            return

        active_sub = db.query(Subscription).filter(
            Subscription.user_id == payment.user_id,
            Subscription.expiry_date > datetime.now(timezone.utc)
        ).first()

        if active_sub and active_sub.level == payment.level:
            active_sub.expiry_date += timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS)
            active_sub.payment_id = payment.id
        else:
            new_sub = Subscription(
                user_id=payment.user_id,
                level=payment.level,
                expiry_date=datetime.now(timezone.utc) + timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS),
                payment_id=payment.id
            )
            db.add(new_sub)
            if active_sub:
                active_sub.expiry_date = datetime.now(timezone.utc)

        db.commit()

    @staticmethod
    def get_user_payments(user_id: int, db: Session) -> List[PaymentResponse]:
        payments = db.query(Payment).filter(Payment.user_id == user_id).all()
        return [PaymentResponse.from_orm(p) for p in payments]

    @staticmethod
    def create_discount(discount_data: DiscountCreate, db: Session) -> DiscountResponse:
        db_discount = Discount(**discount_data.dict())
        db.add(db_discount)
        db.commit()
        db.refresh(db_discount)
        usage_count = db.query(Payment).filter(Payment.discount_id == db_discount.id).count()
        return DiscountResponse.from_orm(db_discount).copy(update={"usage_count": usage_count})

    @staticmethod
    def update_discount(discount_id: int, discount_data: DiscountCreate, db: Session) -> Optional[DiscountResponse]:
        db_discount = db.query(Discount).filter(Discount.id == discount_id).first()
        if not db_discount:
            return None
        for key, value in discount_data.dict().items():
            setattr(db_discount, key, value)
        db.commit()
        db.refresh(db_discount)
        usage_count = db.query(Payment).filter(Payment.discount_id == db_discount.id).count()
        return DiscountResponse.from_orm(db_discount).copy(update={"usage_count": usage_count})

    @staticmethod
    def delete_discount(discount_id: int, db: Session) -> bool:
        db_discount = db.query(Discount).filter(Discount.id == discount_id).first()
        if not db_discount:
            return False
        db.delete(db_discount)
        db.commit()
        return True

    @staticmethod
    def get_discounts(db: Session) -> List[DiscountResponse]:
        discounts = db.query(Discount).all()
        return [
            DiscountResponse.from_orm(d).copy(update={"usage_count": db.query(Payment).filter(Payment.discount_id == d.id).count()})
            for d in discounts
        ]