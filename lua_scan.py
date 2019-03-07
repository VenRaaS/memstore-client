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


if '__main__' == __name__:
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="date with the form of YYYYMMDD, e.g. 20190306 stands for 2019-Mar-06")
    parser.add_argument('table_name',help="table name")
    args = parser.parse_args()

    try:
        datetime.datetime.strptime(args.date, '%Y%m%d')
    except ValueError:
        logging.error("incorrect data format, should be YYYYMMDD")
        exit(1)

    key_pattern = '*_{d}/{t}/*'.format(d=args.date, t=args.table_name)
    logging.info('counting patterned key: "{kp}"'.format(kp=key_pattern))

    lua_script = ' \
        local cursor = "0"; \
        local num_matchs = 0; \
        \
        repeat \
            local matchs = redis.call("SCAN", cursor, "MATCH", KEYS[1], "COUNT", 100); \
            cursor = matchs[1]; \
            num_matchs = num_matchs + #(matchs[2]); \
        until cursor == "0"; \
        \
        return num_matchs; \
    '
    rs_num = rds.eval(lua_script, 1, key_pattern)
    logging.info('#(patterned keys): {n:,}'.format(n=rs_num))

 
