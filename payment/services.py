# src/payment/services.py
from web3 import Web3
from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from payment.models import Payment, Discount
from payment.schemas import PaymentResponse, DiscountCreate, DiscountResponse
from subscription.models import Subscription
from config import settings
import requests
import json

class PaymentService:
    def __init__(self):
        self.tron_wallet_address = settings.TRON_WALLET_ADDRESS
        self.bsc = Web3(Web3.HTTPProvider(settings.BSC_FULL_NODE))
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
            }
        ]
        self.usdt_bep20_contract = self.bsc.eth.contract(
            address=self.usdt_bep20_address,
            abi=self.usdt_bep20_abi
        )

    def generate_unique_amount(self, base_price: float, db: Session) -> float:
        """Generate a unique payment amount to avoid conflicts."""
        amounts_to_try = [
            base_price,
            base_price - 0.01,
            base_price + 0.01,
            base_price - 0.02,
            base_price + 0.02,
        ]
        for amount in amounts_to_try:
            existing_payment = db.query(Payment).filter(
                Payment.amount == int(amount * 100),
                Payment.status == "pending",
                Payment.expiration_time >= datetime.utcnow()
            ).first()
            if not existing_payment:
                return amount
        raise HTTPException(status_code=400, detail="No available unique amount")

    def create_payment(self, amount: float, currency: str, db: Session) -> dict:
        """Create a payment request."""
        if currency == "usdttrc20":
            address = self.tron_wallet_address
        elif currency == "usdtbep20":
            address = self.bsc_wallet_address
        elif currency == "bnb":
            address = self.bsc_wallet_address
        else:
            raise HTTPException(status_code=400, detail="Unsupported currency")
        return {"payment_url": address, "amount": amount}

    def check_payment(self, payment: Payment, db: Session) -> bool:
        """Check payment status in blockchain."""
        amount_in_usd = payment.amount / 100.0
        if payment.currency == "usdttrc20":
            url = f"https://nile.trongrid.io/v1/accounts/{self.tron_wallet_address}/transactions/trc20"
            params = {"contract_address": self.usdt_trc20_address}
            response = requests.get(url, params=params).json()
            for tx in response.get("data", []):
                if (tx["to"] == self.tron_wallet_address and
                    float(tx["value"]) / 10**6 == amount_in_usd):
                    payment.transaction_id = tx["transaction_id"]
                    payment.status = "confirmed"
                    db.commit()
                    return True
        elif payment.currency in ["usdtbep20", "bnb"]:
            latest_block = self.bsc.eth.block_number
            for block in range(latest_block - 100, latest_block + 1):
                if payment.currency == "usdtbep20":
                    try:
                        transfer_events = self.usdt_bep20_contract.events.Transfer.get_logs(
                            fromBlock=block,
                            toBlock=block,
                            argument_filters={"to": self.bsc_wallet_address}
                        )
                        for event in transfer_events:
                            amount_transferred = event["args"]["value"] / 10**18
                            if amount_transferred == amount_in_usd:
                                payment.transaction_id = event["transactionHash"].hex()
                                payment.status = "confirmed"
                                db.commit()
                                return True
                    except Exception:
                        continue
                elif payment.currency == "bnb":
                    block_data = self.bsc.eth.get_block(block, full_transactions=True)
                    for tx in block_data.transactions:
                        if (tx.get("to") == self.bsc_wallet_address and
                            float(tx.get("value", 0)) / 10**18 == amount_in_usd):
                            payment.transaction_id = tx["hash"].hex()
                            payment.status = "confirmed"
                            db.commit()
                            return True
        return False

    @staticmethod
    def get_user_payments(user_id: int, db: Session) -> list[PaymentResponse]:
        """Retrieve all payments for a user."""
        payments = db.query(Payment).join(Subscription).filter(Subscription.user_id == user_id).all()
        return [PaymentResponse.from_orm(payment) for payment in payments]

    @staticmethod
    def create_discount(discount_data: DiscountCreate, db: Session) -> DiscountResponse:
        """Create a new discount."""
        db_discount = Discount(**discount_data.dict())
        db.add(db_discount)
        db.commit()
        db.refresh(db_discount)
        usage_count = db.query(Payment).filter(Payment.discount_id == db_discount.id).count()
        return DiscountResponse(**db_discount.__dict__, usage_count=usage_count)

    @staticmethod
    def update_discount(discount_id: int, discount_data: DiscountCreate, db: Session) -> Optional[DiscountResponse]:
        """Update a discount."""
        db_discount = db.query(Discount).filter(Discount.id == discount_id).first()
        if not db_discount:
            return None
        for key, value in discount_data.dict().items():
            setattr(db_discount, key, value)
        db.commit()
        db.refresh(db_discount)
        usage_count = db.query(Payment).filter(Payment.discount_id == db_discount.id).count()
        return DiscountResponse(**db_discount.__dict__, usage_count=usage_count)

    @staticmethod
    def delete_discount(discount_id: int, db: Session) -> bool:
        """Delete a discount."""
        db_discount = db.query(Discount).filter(Discount.id == discount_id).first()
        if not db_discount:
            return False
        db.delete(db_discount)
        db.commit()
        return True

    @staticmethod
    def get_discounts(db: Session) -> list[DiscountResponse]:
        """Retrieve all discounts."""
        discounts = db.query(Discount).all()
        return [
            DiscountResponse(**discount.__dict__, usage_count=db.query(Payment).filter(Payment.discount_id == discount.id).count())
            for discount in discounts
        ]