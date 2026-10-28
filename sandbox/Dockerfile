# the image the delivered code runs in. It holds Python and behave and
# nothing else: no credentials, no tools to reach out with, nothing of ours.

FROM python:3.12-slim

# the same version the verifier was written against, so the outcome does not
# change between one machine and the next
RUN pip install --no-cache-dir behave==1.3.3

WORKDIR /work
