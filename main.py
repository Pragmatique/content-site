# src/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from auth.routes import router as auth_router
from content.routes import router as content_router
from subscription.routes import router as subscription_router
from payment.routes import router as payment_router
from admin.routes import router as admin_router
from scheduler.tasks import start_scheduler, check_pending_payments

app = FastAPI(
    title="Content Site Backend",
    description="API for content site with media streaming",
    version="0.1.0",
)

# Configure CORS
origins = ["http://localhost:5173", "http://localhost", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(content_router)
app.include_router(subscription_router)
app.include_router(payment_router)
app.include_router(admin_router)

@app.on_event("startup")
async def startup_event():
    """Run initial tasks on startup."""
    check_pending_payments()
    start_scheduler()

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to Content Site Backend!"}