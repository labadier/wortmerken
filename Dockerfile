FROM python:3.11-slim

RUN mkdir /app
RUN chmod a+rw /app

#replace 1001/1007 with user/group id 
# get uid: id -u
# get gid: id -g 
RUN groupadd -g 1001 app && useradd -u 1042 -g app -d /app -s /sbin/nologin -c "non-root app user" app

WORKDIR /workspace
RUN chown -R app:app /workspace
RUN chmod -R a+rw /workspace

COPY --chown=app:app src-python /workspace

RUN python -m pip install --upgrade pip && pip install --root-user-action=ignore -r requirements.txt

RUN mkdir /workspace/output_database 
USER app