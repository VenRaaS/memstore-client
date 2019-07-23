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
                                                                                                                              
class delmskey():

    def del_datePatternedKeys(self, code_name, date):
        # date forms as YYYYMMDD (%Y%m%d)
        key_pattern = '*{cn}_oppoua*'.format(cn=code_name, d=date)
        logger.info('scan and delete patterned key: "{kp}"'.format(kp=key_pattern))

        key2cnt = {}
        keys = []
        for key in rds.scan_iter(key_pattern, 200):
            k_ary = json.loads(key)
            if 2 <= len(k_ary):
                k = ','.join(k_ary[:2])
                key2cnt[k] = key2cnt[k] + 1 if k in key2cnt else 1

            keys.append(key)
            if 200 <= len(keys):
                rds.delete(*keys)
                keys = []
        if 0 < len(keys):
            rds.delete(*keys)

        if 0 < len(key2cnt):
            logging.info('deleted keys which are prefixed as follows ...')
            for k, v in sorted(key2cnt.iteritems()):
                logger.info('{key}: {cnt:,} was deleted'.format(key=k, cnt=v))



if '__main__' == __name__:
   aa = delmskey()
   aa.del_datePatternedKeys('pchome2','20160719')
