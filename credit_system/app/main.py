import os
import pandas as pd
from django.conf import settings
from django.apps import apps
from django.core.management import call_command
from django.http import JsonResponse
from django.urls import path
from datetime import datetime, timedelta
import json
import time
from django.db.utils import OperationalError
import logging
# Django settings configuration
if not settings.configured:
    settings.configure(
        SECRET_KEY='your-secret-key',
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "app",  # Register the app containing models
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "credit_system",
                "USER": "user",
                "PASSWORD": "password",
                "HOST": "db",
                "PORT": "5432",
            }
        },
        MIDDLEWARE=[],
        ROOT_URLCONF=__name__,
        DEBUG=True,
    )

# Populate apps only after settings configuration
apps.populate(settings.INSTALLED_APPS)

# Import models after settings are configured
from app.models import Customer, Loan  # Import models from models.py


def load_data():
    # Load customer data
    if not Customer.objects.exists():
        customer_data = pd.read_excel("customer_data.xlsx")
        customer_data.rename(
            columns={
                "Customer ID": "customer_id",
                "First Name": "first_name",
                "Last Name": "last_name",
                "Age": "age",
                "Phone Number": "phone_number",
                "Monthly Salary": "monthly_salary",
                "Approved Limit": "approved_limit",
            },
            inplace=True,
        )
        for _, row in customer_data.iterrows():
            Customer.objects.create(
                first_name=row["first_name"],
                last_name=row["last_name"],
                age=row["age"],  # New field added
                phone_number=row["phone_number"],
                monthly_salary=row["monthly_salary"],
                approved_limit=row["approved_limit"],
            )

    # Load loan data
    if not Loan.objects.exists():
        loan_data = pd.read_excel("loan_data.xlsx")
        loan_data.rename(
            columns={
                "Loan ID": "loan_id",
                "Customer ID": "customer_id",
                "Loan Amount": "loan_amount",
                "Tenure": "tenure",
                "Interest Rate": "interest_rate",
                "Monthly payment": "monthly_repayment",
                "EMIs paid on Time": "emis_paid_on_time",
                "Date of Approval": "date_of_approval",
                "End Date": "end_date",
            },
            inplace=True,
        )
        for _, row in loan_data.iterrows():
            customer = Customer.objects.get(customer_id=row["customer_id"])
            date_of_approval = row["date_of_approval"].strftime('%Y-%m-%d') if isinstance(row["date_of_approval"], pd.Timestamp) else row["date_of_approval"]
            end_date = row["end_date"].strftime('%Y-%m-%d') if isinstance(row["end_date"], pd.Timestamp) else row["end_date"]
            Loan.objects.create(
                customer=customer,
                loan_amount=row["loan_amount"],
                tenure=row["tenure"],
                interest_rate=row["interest_rate"],
                monthly_installment=row["monthly_repayment"],
                emis_paid_on_time=bool(row["emis_paid_on_time"]),  # New field added
                date_of_approval=date_of_approval,
                end_date=end_date,
            )

# Helper function to calculate monthly installment using compound interest
def calculate_monthly_installment(principal, rate, tenure):
    rate = rate / (12 * 100)  # Monthly interest rate
    tenure_months = tenure * 12
    if rate == 0:
        return principal / tenure_months
    return principal * rate * ((1 + rate) ** tenure_months) / (((1 + rate) ** tenure_months) - 1)



# /register
from django.http import JsonResponse
import json

def register(request):
    if request.method == "POST":
        try:
            # Handle both JSON and form-data
            if request.content_type == "application/json":
                data = json.loads(request.body)  # Parse JSON body
            else:
                data = request.POST  # Parse form-data

            # Validate required fields
            required_fields = ["first_name", "last_name", "age", "monthly_income", "phone_number"]
            for field in required_fields:
                if field not in data:
                    return JsonResponse({"error": f"Missing '{field}' in request data"}, status=400)

            # Calculate approved limit
            approved_limit = round((int(data["monthly_income"]) * 36) / 100000) * 100000

            # Create a new customer
            customer = Customer.objects.create(
                first_name=data["first_name"],
                last_name=data["last_name"],
                age=int(data["age"]),
                phone_number=data["phone_number"],
                monthly_salary=int(data["monthly_income"]),
                approved_limit=approved_limit,
            )

            # Return response
            return JsonResponse({
                "customer_id": customer.customer_id,
                "name": f"{customer.first_name} {customer.last_name}",
                "age": customer.age,
                "monthly_income": customer.monthly_salary,
                "approved_limit": customer.approved_limit,
                "phone_number": customer.phone_number,
            })
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)



# /check-eligibility
def check_eligibility(request):
    if request.method == "POST":
        try:
            # Handle both JSON and form-data
            if request.content_type == "application/json":
                data = json.loads(request.body)  # Parse JSON body
            else:
                data = request.POST  # Parse form-data

            # Validate required fields
            required_fields = ["customer_id", "loan_amount", "interest_rate", "tenure"]
            for field in required_fields:
                if field not in data:
                    return JsonResponse({"error": f"Missing '{field}' in request data"}, status=400)

            # Fetch customer
            customer = Customer.objects.get(customer_id=data["customer_id"])

            # Load loan data to calculate credit score
            loan_data = pd.read_excel("loan_data.xlsx")
            loans = loan_data[loan_data["Customer ID"] == customer.customer_id]

            total_loans = loans["Loan Amount"].sum()
            loans_this_year = loans[loans["Date of Approval"].apply(lambda d: d.year if isinstance(d, pd.Timestamp) else datetime.strptime(d, '%Y-%m-%d').year) == datetime.now().year]


            credit_score = 50
            if total_loans > customer.approved_limit:
                credit_score = 0

            corrected_interest_rate = float(data["interest_rate"])
            if credit_score > 50:
                approval = True
            elif 30 < credit_score <= 50:
                approval = True
                corrected_interest_rate = max(12, corrected_interest_rate)
            elif 10 < credit_score <= 30:
                approval = True
                corrected_interest_rate = max(16, corrected_interest_rate)
            else:
                approval = False

            monthly_installment = calculate_monthly_installment(
                float(data["loan_amount"]),
                corrected_interest_rate,
                int(data["tenure"])
            )

            total_emis = sum(loan.monthly_installment for loan in Loan.objects.filter(customer=customer))
            if total_emis + monthly_installment > 0.5 * customer.monthly_salary:
                approval = False

            return JsonResponse({
                "customer_id": customer.customer_id,
                "approval": approval,
                "interest_rate": float(data["interest_rate"]),
                "corrected_interest_rate": corrected_interest_rate,
                "tenure": int(data["tenure"]),
                "monthly_installment": monthly_installment,
            })
        except Customer.DoesNotExist:
            return JsonResponse({"error": "Customer not found"}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)



# /create-loan

def create_loan(request):
    if request.method == "POST":
        try:
            # Handle JSON and form-data
            if request.content_type == "application/json":
                data = json.loads(request.body)  # Parse JSON body
            else:
                data = request.POST  # Parse form-data

            # Validate required fields
            required_fields = ["customer_id", "loan_amount", "interest_rate", "tenure"]
            for field in required_fields:
                if field not in data:
                    return JsonResponse({"error": f"Missing '{field}' in request data"}, status=400)

            # Fetch customer
            customer = Customer.objects.get(customer_id=data["customer_id"])
            loan_amount = float(data["loan_amount"])
            interest_rate = float(data["interest_rate"])
            tenure = int(data["tenure"])
            monthly_installment = calculate_monthly_installment(loan_amount, interest_rate, tenure)

            # Check if the loan exceeds eligibility criteria
            total_existing_emis = sum(loan.monthly_installment for loan in Loan.objects.filter(customer=customer))
            if total_existing_emis + monthly_installment > 0.5 * customer.monthly_salary:
                return JsonResponse({
                    "loan_id": None,
                    "customer_id": customer.customer_id,
                    "loan_approved": False,
                    "message": "Loan not approved: EMIs exceed 50% of monthly salary.",
                    "monthly_installment": monthly_installment,
                })

            # Calculate dates
            date_of_approval = datetime.now()
            end_date = date_of_approval + timedelta(days=tenure * 365)

            # Create the loan
            loan = Loan.objects.create(
                customer=customer,
                loan_amount=loan_amount,
                tenure=tenure,
                interest_rate=interest_rate,
                monthly_installment=monthly_installment,
                date_of_approval=date_of_approval,
                end_date=end_date,
            )
            return JsonResponse({
                "loan_id": loan.loan_id,
                "customer_id": customer.customer_id,
                "loan_approved": True,
                "message": "Loan approved successfully.",
                "monthly_installment": loan.monthly_installment,
                "date_of_approval": loan.date_of_approval,
                "end_date": loan.end_date,
            })
        except Customer.DoesNotExist:
            return JsonResponse({"error": "Customer not found"}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)



# /view-loan/<loan_id>
def view_loan(request, loan_id):
    if request.method == "GET":
        loan = Loan.objects.get(loan_id=loan_id)
        customer = loan.customer
        return JsonResponse({
            "loan_id": loan.loan_id,
            "customer": {
                "id": customer.customer_id,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "phone_number": customer.phone_number,
                "age": customer.age,
            },
            "loan_amount": loan.loan_amount,
            "interest_rate": loan.interest_rate,
            "monthly_installment": loan.monthly_installment,
            "tenure": loan.tenure,
        })


# /view-loans/<customer_id>
def view_loans(request, customer_id):
    if request.method == "GET":
        customer = Customer.objects.get(customer_id=customer_id)
        loans = Loan.objects.filter(customer=customer)
        loan_list = [{
            "loan_id": loan.loan_id,
            "loan_amount": loan.loan_amount,
            "interest_rate": loan.interest_rate,
            "monthly_installment": loan.monthly_installment,
            "repayments_left": loan.tenure * 12,  # Correct logic: tenure in years * 12
        } for loan in loans]
        return JsonResponse(loan_list, safe=False)




# URL patterns
urlpatterns = [
    path("register", register),
    path("check-eligibility", check_eligibility),
    path("create-loan", create_loan),
    path("view-loan/<int:loan_id>", view_loan),
    path("view-loans/<int:customer_id>", view_loans),
]

def wait_for_db():
    retries = 10  # Number of retries
    while retries > 0:
        try:
            call_command("check", database=["default"])
            print("Database is ready.")
            return
        except OperationalError:
            print("Database not ready. Retrying in 5 seconds...")
            retries -= 1
            time.sleep(5)
    raise Exception("Database is not ready after several attempts.")
    
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
# Main function
def main():
    try:
        logging.info("Starting database setup...")
        wait_for_db()
        call_command("makemigrations", "app")  # Regenerate migrations for the app
        call_command("migrate")  # Apply migrations
        logging.info("Database migrations applied successfully.")
        logging.info("Loading initial data...")
        load_data()  # Load data
        
        logging.info("Starting server...")
        call_command("runserver", "0.0.0.0:8000")  # Start server
        logging.info("Server is running at http://localhost:8000")
        logging.info("Press Ctrl+C to stop the server.")
    except Exception as e:
        logging.error(f"Error during startup: {e}")



if __name__ == "__main__":
    main()
