import logging
import argparse
import json
import redis
import threading
from multiprocessing import Pool, Value



logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %I:%M:%S')

#-- redis-py, see https://github.com/andymccurdy/redis-py
rds = redis.StrictRedis(host='10.0.0.3', port=6379)

#TODO paramtize expire_sec_mpv
expire_sec_mpv = Value('i', 864)


def rds_get(k):
    global rds
    
    rt = None
    try:
        rt = rds.get(k)
    except Exception as e:
        logging.error(e, exc_info=True)

    return rt


def rds_setex(t_kv):
    global rds
    
    try:
        key, value = t_kv
        rds.setex(key, expire_sec_mpv.value, value)

    except Exception as e:
        logging.error(e, exc_info=True)


if '__main__' == __name__:
    jkey_c = 'code_name'
    jkey_t = 'table_name'
    jkey_i = 'id'
    jkey_v = 'indicators_raw'

    parser = argparse.ArgumentParser()
    parser.add_argument("src_fp", help="source file path")
    parser.add_argument("-c", "--{}".format(jkey_c), help="source json key represents code name, default: {}".format(jkey_c))
    parser.add_argument("-t", "--{}".format(jkey_t), help="source json key represents table/mode name, default: {}".format(jkey_t))
    parser.add_argument("-i", "--{}".format(jkey_i), help="source json key represents gid/category/item/rule id, default: {}".format(jkey_i))
    parser.add_argument("-v", "--{}".format(jkey_v), help="source json key represents rule/recomd list, default: {}".format(jkey_v))
    args = parser.parse_args()

    if getattr(args, jkey_c): jkey_c = getattr(args, jkey_c)
    if getattr(args, jkey_t): jkey_t = getattr(args, jkey_t)
    if getattr(args, jkey_i): jkey_i = getattr(args, jkey_i)
    if getattr(args, jkey_v): jkey_v = getattr(args, jkey_v)
#    print jkey_c
#    print jkey_t
#    print jkey_i
#    print jkey_v
  
    logging.info('{} counting ...'.format(args.src_fp))
    size_src = 0.0
    with open(args.src_fp, 'r') as f:
        for i, l in enumerate(f):
            size_src = i
            pass
    size_src += 1.0
    logging.info('{} has {:.0f} item ruls'.format(args.src_fp, size_src))

    pool = Pool(processes = 512)
    
    with open(args.src_fp, 'r') as f:
        keys = []
        vals = []

        for i_line, l in enumerate(f):
            j = json.loads(l)

            if not jkey_c in j:
                logging.error('{} is not found at line:{} in {}'.format(jkey_c, i_line, args.src_fp))
                continue
            if not jkey_t in j:
                logging.error('{} is not found at line:{} in {}'.format(jkey_t, i_line, args.src_fp))
                continue
            if not jkey_i in j:
                logging.error('{} is not found at line:{} in {}'.format(jkey_i, i_line, args.src_fp))
                continue
            if not jkey_v in j:
                logging.error('{} is not found at line:{} in {}'.format(jkey_v, i_line, args.src_fp))
                continue

            k = '{c}.{t}.{i}'.format(c=j[jkey_c], t=j[jkey_t], i=j[jkey_i])
            v = j[jkey_v]
            keys.append(k)
            vals.append(v)
    
            if i_line % 30000 == 0:
                tKB_list = zip(keys, vals)
                pool.map(rds_setex, tKB_list)
#                pool.map(rds_get, keys)

                keys = []
                vals = []

                logging.info('{:.0f} {:.0f}%'.format(i_line, i_line / size_src * 100))
            
        tKB_list = zip(keys, vals)
        pool.map(rds_setex, tKB_list)

    logging.info('{:.0f} {:.0f}%'.format(size_src, 100.0))


