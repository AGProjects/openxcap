# Access to OpenSIPS database, replace opensips with the name of the real database
# Replace PASSWORD and PRIVATE_IP_NETWORK with real values

GRANT ALL ON opensips.* TO openxcap@'localhost' IDENTIFIED by 'PASSWORD';
GRANT ALL ON opensips.* TO openxcap@'PRIVATE_IP_NETWORK.%' IDENTIFIED by 'PASSWORD';
