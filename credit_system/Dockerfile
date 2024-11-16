FROM python:3.10-slim

WORKDIR /wdir

COPY ./app /wdir/app
COPY requirements.txt /wdir/requirements.txt
COPY ./app/customer_data.xlsx /wdir/customer_data.xlsx
COPY ./app/loan_data.xlsx /wdir/loan_data.xlsx

ENV PYTHONPATH=/wdir

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "app/main.py"]
