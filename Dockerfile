FROM alpine:latest
 
LABEL maintainer="František Polášek <iam@parallelo3301.org>"
 
RUN apk add python3 py3-pip py3-wheel

COPY ./requirements.txt /requirements.txt

RUN pip install -r /requirements.txt && \
    rm -rf /requirements.txt

COPY ./bot.py /app/bot.py

WORKDIR /app

CMD ["python3", "bot.py"]

