FROM python:3.6

WORKDIR /app
COPY *.py /app
COPY requirements.txt /app
COPY gitlab.cfg /app

RUN pip install -r requirements.txt

EXPOSE 5000

CMD ["python", "main.py"]
