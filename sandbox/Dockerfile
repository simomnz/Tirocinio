# the image the delivered code runs in. It holds Python and behave and
# nothing else: no credentials, no tools to reach out with, nothing of ours.

# pinned by digest and not by tag: python:3.12-slim is a moving name, and the
# comment below promises an outcome that does not change between one machine
# and the next. Only a digest keeps that promise. To move to a newer base,
# read its digest with: docker pull python:3.12-slim &&
#   docker image inspect python:3.12-slim --format '{{index .RepoDigests 0}}'
FROM python@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

# the same version the verifier was written against, so the outcome does not
# change between one machine and the next
RUN pip install --no-cache-dir behave==1.3.3

WORKDIR /work
