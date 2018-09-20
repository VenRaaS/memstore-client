import os, sys, time 
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


##
## simulates the linux command, e.g. tail -F [file]
## see http://man7.org/linux/man-pages/man1/tail.1.html
##
def tail_file(fname, cbf, seconds_sleep=1):
    cur_f = open(fname, 'r')
    cur_ino = os.fstat(cur_f.fileno()).st_ino
    cur_f.seek(0, os.SEEK_END)
    
    try:
        while True:
            while True:
                lines = cur_f.readlines(5 * 1024 * 1024)
                cbf(lines)
                time.sleep(seconds_sleep)

                if not lines:
                    logging.info('EOF')
                    break

            try:
                #-- reopen the file if the old log file is rotated 
                if os.stat(fname).st_ino != cur_ino:
                    cur_f.close()
                    new_f = open(fname, 'r')
                    cur_f = new_f 
                    cur_ino = os.fstat(cur_f.fileno()).st_ino
                    logging.info('{0} inode changed, reopen the file'.format(fname))
            except IOError as e:
                logging.error(e)

    except KeyboardInterrupt as e:
        logging.error(e, exc_info=True)

    finally:
        if not cur_f.closed:
            cur_f.close()


def pool_sync(lines):
#    TODO...
    pass
#    if len(lines):
#        j = json.loads(lines[0])
#        if 'code_name' in j:
#            logging.info(j['code_name'])


def tail_sync_file(rds, args):
    tail_file(args.src_fp, pool_sync)
    

def batch_sync_file(rds, args) :
    jkey_c = args.c 
    jkey_t = args.t
    jkey_i = args.i
    jkey_v = args.v
    if args.ttl: expire_sec_mpv.value = args.ttl
    logging.info('combo key: ${0}.${1}.${2}'.format(jkey_c, jkey_t, jkey_i))
    logging.info('value key: {0}'.format(jkey_v))
    logging.info('ttl: {0}'.format(args.ttl))
    logging.info('command: {0}'.format(args.cmd))
    exit()

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


if '__main__' == __name__:
    parser = argparse.ArgumentParser()
    parser.add_argument("src_fp", help="source file path")
    subparsers = parser.add_subparsers(help='sub-command help')

    jkey_c = 'code_name'
    jkey_t = 'table_name'
    jkey_i = 'id'
    jkey_v = 'indicators_raw'
    parser_bat = subparsers.add_parser("batch", help="sync file all at once")
    parser_bat.add_argument("cmd", default="set", help="set, rpush")
    parser_bat.add_argument("-c", default="{0}".format(jkey_c), help="source json key represents code name, default: {0}".format(jkey_c))
    parser_bat.add_argument("-t", default="{0}".format(jkey_t), help="source json key represents table/mode name, default: {0}".format(jkey_t))
    parser_bat.add_argument("-i", default="{0}".format(jkey_i), help="source json key represents gid/category/item/rule id, default: {0}".format(jkey_i))
    parser_bat.add_argument("-v", default="{0}".format(jkey_v), help="source json key represents rule/recomd list, default: {0}".format(jkey_v))
    parser_bat.add_argument("-ttl", default=86400, help="live time of keys, default: {0} seconds".format(86400))
    parser_bat.set_defaults(func = batch_sync_file)

    parser_tail = subparsers.add_parser("tail", help="sync once file grows")
    parser_tail.set_defaults(func = tail_sync_file)
 
    args = parser.parse_args()
    args.func(rds, args)
  

