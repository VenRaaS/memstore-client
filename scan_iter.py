import logging
import argparse
import json
import redis
import datetime
from multiprocessing import Pool, Value


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(filename)s:%(lineno)d [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %I:%M:%S')

#-- redis-py, see https://github.com/andymccurdy/redis-py
HOST_RDS = 'ms-node-01'
PORT_RDS = '6379'
TIMEOUT_IN_SEC = 10
rds = redis.StrictRedis(host=HOST_RDS, port=6379, socket_connect_timeout=TIMEOUT_IN_SEC)

COUNT_ITERSTION_SIZE = 200


if '__main__' == __name__:
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="date with the form of YYYYMMDD, e.g. 20190306 stands for 2019-Mar-06")
    args = parser.parse_args()

    try:
        datetime.datetime.strptime(args.date, '%Y%m%d')
    except ValueError:
        logging.error("incorrect data format, should be YYYYMMDD")
        exit(1)

    key_pattern = '*_{d}/*'.format(d=args.date)
    logging.info('counting patterned key: "{kp}"'.format(kp=key_pattern))

    key2cnt = {}
    keys = []
    for key in rds.scan_iter(key_pattern, COUNT_ITERSTION_SIZE):
        ks = key.split('/')
        k = '/'.join(ks[:3])
        
        key2cnt[k] = key2cnt[k] + 1 if k in key2cnt else 1

        keys.append(key)
        if COUNT_ITERSTION_SIZE <= len(keys):
#            rds.delete(*keys)
            keys = []
#    rds.delete(*key)
    
#    logging.info('the following patterned keys have beed deleted.')
    for k, v in key2cnt.iteritems():
        logging.info('{key}: {cnt:,} '.format(key=k, cnt=v))


