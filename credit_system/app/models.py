from django.db import models


class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    age = models.IntegerField()  # Added to match the Age column in Excel
    phone_number = models.CharField(max_length=15)
    monthly_salary = models.IntegerField()
    approved_limit = models.IntegerField()
    current_debt = models.IntegerField(default=0)

    class Meta:
        app_label = "app"


class Loan(models.Model):
    loan_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    loan_amount = models.FloatField()
    tenure = models.IntegerField()  # In years
    interest_rate = models.FloatField()
    monthly_installment = models.FloatField()
    emis_paid_on_time = models.BooleanField(default=True)  # Based on "EMIs paid on Time"
    date_of_approval = models.DateField()  # Matches "Date of Approval"
    end_date = models.DateField()  # Matches "End Date"

    class Meta:
        app_label = "app"
