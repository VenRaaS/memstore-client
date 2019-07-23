import os
import sys
import logging
from datetime import datetime, timedelta
import requests
import redis
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d %(message)s', datefmt='%Y-%m-%d %I:%M:%S')
logger = logging.getLogger(__file__)

#-- redis-py, see https://github.com/andymccurdy/redis-py
HOST_RDS = 'ms-node-01'
PORT_RDS = '6379'
TIMEOUT_IN_SEC = 10
rds = redis.StrictRedis(host=HOST_RDS, port=6379, socket_connect_timeout=TIMEOUT_IN_SEC)

class countmskey():

    def key2count_GroupByKeyPrefix(self, code_name, date):
        # date forms as YYYYMMDD (%Y%m%d)
        key_pattern = '*{cn}_*_{d}*'.format(cn=code_name, d=date)
        logger.info('counting patterned key: "{kp}"'.format(kp=key_pattern))

        key2cnt = {}
        for key in rds.scan_iter(key_pattern, 200):
            k_ary = json.loads(key)
            if 2 <= len(k_ary):
                k = ','.join(k_ary[:2])
                key2cnt[k] = key2cnt[k] + 1 if k in key2cnt else 1

        return key2cnt

if '__main__' == __name__:
   aa =  countmskey()
   key2cnt_latest=aa.key2count_GroupByKeyPrefix('pchome2','20160719')
   for k, v in sorted(key2cnt_latest.iteritems()):
        logger.info('[{key}]: {cnt:,} '.format(key=k, cnt=v))
