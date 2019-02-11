import os, sys, time 
import logging
import argparse
import json
import redis
import threading
import glob
import subprocess
import time
import re
from multiprocessing import Pool, Value



logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %I:%M:%S')

#-- redis-py, see https://github.com/andymccurdy/redis-py
HOST_RDS = 'ms-westernwall'
PORT_RDS = '6379'
TIMEOUT_IN_SEC = 1
rds = redis.StrictRedis(host=HOST_RDS, port=6379, socket_connect_timeout=TIMEOUT_IN_SEC)

SLEEP_FOR_FILE_CHANGE_DETECTION_IN_SEC = 300

expire_sec_mpv = Value('i', 0)



##
## pipelining
## see https://github.com/andymccurdy/redis-py#pipelines,
##     https://redis.io/topics/pipelining,
##     https://redis.io/topics/mass-insert
##
def rds_pipe_worker(tuple_list):
    try:
        #-- disable the atomic nature of a pipeline
        #   see https://github.com/andymccurdy/redis-py#pipelines
        with rds.pipeline(transaction=False) as pipe:
            for args, rdscmds in tuple_list:
                for cmd in rdscmds:
                    if RedisCommand.append == cmd[0]:
                        k, v = cmd[1:] 
                        pipe.append(k, '{_v},'.format(_v=v))
                    elif RedisCommand.set == cmd[0]:
                        k, v = cmd[1:] 
                        pipe.set(k, v)
                    elif RedisCommand.get == cmd[0]:
                        k = cmd[1] 
                        pipe.get(k)
                    elif RedisCommand.rpush == cmd[0]:
                        k, v = cmd[1:] 
                        pipe.rpush(k, v)
                    elif RedisCommand.lpush == cmd[0]:
                        k, v = cmd[1:] 
                        pipe.lpush(k, v)
                    elif RedisCommand.ltrim == cmd[0]:
                        k, start, stop = cmd[1:]
                        pipe.ltrim(k, start, stop)
                    elif RedisCommand.expire == cmd[0]:
                        k, v = cmd[1:] 
                        pipe.expire(k, v)
                    elif RedisCommand.zadd == cmd[0]:
                        k, s, v = cmd[1:] 
                        pipe.zadd(k, s, v)
                    elif RedisCommand.zremrangebyscore == cmd[0]:
                        k, minscore, maxscore = cmd[1:]
                        pipe.zremrangebyscore(k, minscore, maxscore)
                    elif RedisCommand.zremrangebyrank == cmd[0]:
                        k, start, stop = cmd[1:]
                        pipe.zremrangebyrank(k, start, stop)

            pipe.execute()
            logging.info('pipelining {:,} rows'.format(len(tuple_list)))
    except KeyboardInterrupt as e:
        logging.error(e, exc_info=True)


##
## simulates the linux command, e.g. tail -F [file]
## see http://man7.org/linux/man-pages/man1/tail.1.html
##
def tail_file(args, parser_cbf, seconds_sleep=3):
    fname = args.src_fp
    cur_f = open(fname, 'r')
    cur_ino = os.fstat(cur_f.fileno()).st_ino
    
    #-- move to start read position  
    if args.startfromend:
        cur_f.seek(0, os.SEEK_END)
    
    try:
        while True:
            while True:
                lines = cur_f.readlines(10 * 1024 * 1024)
#                print lines
                if 0 < len(lines):
                    parser_cbf(args, fname, 0, lines)

                if not lines:
                    logging.info('EOF')
                    time.sleep(seconds_sleep)
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


def tail_sync_file(args):
    tail_file(args, weblog_td_parser)


def pipe_file(args, parser_cbf):
    state_files = FilesState(args.src_fp, args.deamon)
    new_state_files = state_files 
    while True:
        for fn in new_state_files.get_fnames():
            if new_state_files != state_files:
                s = state_files.get_state(fn)
                if s:
                    s_new = new_state_files.get_state(fn)
                    if s_new['ino'] == s['ino'] and s_new['md5'] == s['md5']:
                        logging.info('{n} has not change detected'.format(n=fn))
                        continue

            logging.info('{} counting ...'.format(fn))
            size_src = 0.0
            with open(fn, 'r') as f:
                for i, l in enumerate(f):
                    size_src = i
                    pass
            size_src += 1.0
            logging.info('{} has {:,.0f} records'.format(fn, size_src))
            
            with open(fn, 'r') as f:
                size = 0
                while True:
                    lines = f.readlines(30 * 1024 * 1024)
                    if 0 < len(lines):
                        parser_cbf(args, fn, size, lines)
                    else:
                        break

                    size += len(lines)
                    logging.info('{:,.0f} {:,.0f}%'.format(size, size / size_src * 100))

        if not args.deamon:
            break
        
        time.sleep(SLEEP_FOR_FILE_CHANGE_DETECTION_IN_SEC)
        new_state_files = FilesState(args.src_fp, args.deamon)


def pipe_sync_file(args):
    if IndexCategory.gocc == args.index_cat or \
        IndexCategory.mod == args.index_cat:
        jkey_c = args.c 
        jkey_t = args.t
        jkey_k = args.k
        jkeys_vals = args.valkeys
        logging.info('combo key: ${0}.${1}.${2}'.format(jkey_c, jkey_t, jkey_k))
        logging.info('value key: {0}'.format(jkeys_vals))
        logging.info('ttl: {0}'.format(args.ttl))
        logging.info('deamon mode: {0}'.format(args.deamon))
        pipe_file(args, goccmod_parser)

    elif IndexCategory.weblogtd == args.index_cat:
        pipe_file(args, weblog_td_parser)


def weblog_td_parser(args, fn, cntbase, lines):
    tuple_list = []
    try:
        for i_line, l in enumerate(lines):
            cols = l.split('\t')
            js = json.loads(cols[-1])
            if args.c not in js or 'logbody' not in js or 'action' not in js or 'logdt' not in js \
                or not js[args.c] or not js['action'] or not js ['logdt']:
                logging.error('invalid weblog due to lack of some basic key-value pairs')
                continue
            
            cn = js[args.c]
            act = js['action']
            logdt = js ['logdt']

            rdscmds = []
            js = json.loads(js['logbody'])
            if act in js.keys():
                js = json.loads(js[act][0])

                #-- oua
                if 'ven_guid' in js and 'uid' in js and js['ven_guid'] and js['uid']:
                    k = '/{c}_oua/OnlineUserAlign/_search_last_login_uid?q=ven_guid:{i}'.format(
                        c = cn, i = js['ven_guid'])
                    v = {'uid':js['uid']}
                    if logdt:
                        score = float(re.sub('[- :T]', '', logdt)[:14])
                        rdscmds.append((RedisCommand.zadd, k, score, v))
                        rdscmds.append((RedisCommand.zremrangebyrank, k, 0, -6))
                        rdscmds.append((RedisCommand.expire, k, args.ttl))
                    else:
                        logging.error('{} is not found at line:{} in {}'.format('logdt', i_line+cntbas, fn))

                    k = '/{c}_oua/OnlineUserAlign/_search_last_ven_guids?q=uid:{i}'.format(
                        c = cn, i = js['uid'])
                    v = {'ven_guid':js['ven_guid']}
                    if logdt:
                        score = float(re.sub('[- :T]', '', logdt)[:14])
                        rdscmds.append((RedisCommand.zadd, k, score, v))
                        rdscmds.append((RedisCommand.zremrangebyrank, k, 0, -6))
                        rdscmds.append((RedisCommand.expire, k, args.ttl))
                    else:
                        logging.error('{} is not found at line:{} in {}'.format('logdt', i_line+cntbas, fn))

                #-- opp 
                if 'pageload' == act and 'ven_guid' in js \
                    and 'gid' in js and 'categ_code' in js \
                    and js['gid'] and js['categ_code']:
                    k = '/{c}_opp/OnlinePref/{act}/_search_last_gop_ops?q=ven_guid:{i}'.format(
                        c = cn, act = act, i = js['ven_guid'])
                    v = {'gid':js['gid'], 'category_code':js['categ_code'], 'insert_dt':logdt}

                    rdscmds.append((RedisCommand.lpush, k, v))
                    rdscmds.append((RedisCommand.ltrim, k, 0, 60))
                    rdscmds.append((RedisCommand.expire, k, args.ttl))

                #-- checkout
                if 'checkout' == act \
                    and 'trans_i' in js and js['trans_i'] \
                    and 'ven_guid' in js and 'uid' in js and js['ven_guid'] and js['uid']:
                    k = '/{c}_opp/OnlinePref/{act}/_search_last_checkout_gids?q=ven_guid:{i}'.format(
                        c = cn, act = act, i = js['ven_guid'])
                    v = {'trans_i':js['trans_i']}

                    rdscmds.append((RedisCommand.lpush, k, v))
                    rdscmds.append((RedisCommand.ltrim, k, 0, 10))
                    rdscmds.append((RedisCommand.expire, k, args.ttl))

                #-- unfavadd
                if 'unfavadd' == act \
                    and 'ven_guid' in js and 'gid' in js \
                    and js['ven_guid'] and js['gid']:
                    k = '/{c}_opp/OnlinePref/{act}?q=ven_guid:{i}'.format(
                        c = cn, act = act, i = js['ven_guid'])
                    v = {'gid':js['gid']}

                    rdscmds.append((RedisCommand.lpush, k, v))
                    rdscmds.append((RedisCommand.ltrim, k, 0, 20))
                    rdscmds.append((RedisCommand.expire, k, args.ttl))

                if 0 < len(rdscmds):
                    tuple_list.append( (args, rdscmds) )
        rds_pipe_worker(tuple_list)
    except Exception as e:
        logging.error(e, exc_info=True)


def goccmod_parser(args, fn, cntbase, lines):
    jkey_c = args.c 
    jkey_t = args.t
    jkey_k = args.k
    jkeys_vals = args.valkeys

    tuple_list = []
    for i_line, l in enumerate(lines):
        try:
            j = json.loads(l)

            if not jkey_c in j:
                logging.error('{} is not found at line:{} in {}'.format(jkey_c, i_line+cntbas, fn))
                continue
            if not jkey_t in j:
                logging.error('{} is not found at line:{} in {}'.format(jkey_t, i_line+cntbase, fn))
                continue
            if not jkey_k in j:
                logging.error('{} is not found at line:{} in {}'.format(jkey_k, i_line+cntbase, fn))
                continue

            if jkeys_vals:
                for vk in jkeys_vals:
                    if not vk in j:
                        logging.error('{} is not found at line:{} in {}'.format(vk, i_line, fn))
                        continue

            idkey = jkey_k.lower() if args.lowercase_idkey else jkey_k
            k = '/{c}_{ic}/{t}/_search?q={k}:{i}'.format(c=j[jkey_c], ic=args.index_cat, t=j[jkey_t], k=idkey, i=j[jkey_k])

            v_obj = {}
            if jkeys_vals:
                for vk in jkeys_vals:
                    if args.lowercase_valkeys:
                        v_obj[vk.lower()] = j[vk]
                    else:
                        v_obj[vk] = j[vk]
            else:
                v_obj = j
            v = json.dumps(v_obj, ensure_ascii=False).encode('utf8')

            rdscmds = []
            if 'goods' == j[args.t] or \
               'category' == j[args.t] or \
               'cooc_pn' == j[args.t] or \
               'vig' == j[args.t] or \
               'tp' == j[args.t]:
                rdscmds.append((RedisCommand.lpush, k, v))
                rdscmds.append((RedisCommand.ltrim, k, 0, 0))
                rdscmds.append((RedisCommand.expire, k, args.ttl))
            elif 'breadcrumb' == j[args.t] or \
                 'goods_category_flatten' == j[args.t]:
                if not args.datetimekey:
                    logging.error('--datetimekey is not specified')
                    break

                if args.datetimekey not in j:
                    logging.error('{} is not found at line:{} in {}'.format(args.datetimekey, i_line+cntbase, fn))
                    continue

                #-- extract YYYYMMDD as score
                dt = j[args.datetimekey]
                score = float(re.sub('[- ]', '', dt)[:8])
                score_yest = score - 1
                rdscmds.append((RedisCommand.zadd, k, score, v))
                rdscmds.append((RedisCommand.zremrangebyscore, k, '-inf', score_yest))
                rdscmds.append((RedisCommand.expire, k, args.ttl))

            tuple_list.append((args, rdscmds))
        except Exception as e:
            logging.error(e, exc_info=True)

    rds_pipe_worker(tuple_list)


class FilesState:
    def __init__(self, fpattern, dohash=False):
        logging.info('find all pathnames matching pattern \"{p}\" ...'.format(p=fpattern))
        self.fnames = sorted(glob.glob(fpattern))
        self.fname2state = {}

        for fn in self.fnames:
            logging.info('collecting {n} state ...'.format(n=fn))
            self.fname2state[fn] = {}
            self.fname2state[fn]['ino'] = os.stat(fn).st_ino
            self.fname2state[fn]['mtime'] = os.stat(fn).st_mtime
            if dohash:
                self.fname2state[fn]['md5'] = subprocess.check_output(['md5sum', fn]).strip().split()[0]

    def get_fnames(self):
        return self.fnames
    
    def get_state(self, fname):
        return self.fname2state.get(fname) 

from enum import Enum
class IndexCategory(Enum):
    gocc = 'gocc'
    mod = 'mod'
    weblogtd = 'weblogtd'

    def __str__(self):
        return self.value

class RedisCommand(Enum):
    append = 'append'
    get = 'get'
    set = 'set'
    rpush = 'rpush'
    lpush = 'lpush'
    ltrim = 'ltrim'
    expire = 'expire'
    zadd = 'zadd'
    zremrangebyscore = 'zremrangebyscore'
    zremrangebyrank = 'zremrangebyrank'

    def __str__(self):
        return self.value

if '__main__' == __name__:
    parser = argparse.ArgumentParser()
    parser.add_argument("src_fp", help="source file path")
    parser.add_argument('index_cat', type=IndexCategory, choices=list(IndexCategory), help="index category")

    jkey_c = 'code_name'
    jkey_t = 'table_name'
    jkey_k = 'id'
    parser.add_argument("-c", default="{0}".format(jkey_c), help="the key for code name, default: {0}".format(jkey_c))
    parser.add_argument("-t", default="{0}".format(jkey_t), help="the key for table/mode name, default: {0}".format(jkey_t))
    parser.add_argument("-k", default="{0}".format(jkey_k), help="the key for key/gid/item id, default: {0}".format(jkey_k))
    parser.add_argument("-v", "--valkeys", action='append', help="the key for value/rule content, default: all")
    parser.add_argument("-lk", "--lowercase_idkey", action='store_true', help="lower case the key of key/gid/item id, default: false")
    parser.add_argument("-lv", "--lowercase_valkeys", action='store_true', help="lower case the key of value/rule, default: false")
    parser.add_argument("-dt", "--datetimekey", help="source json key of datetime field for sorted score")
    parser.add_argument("-ttl", "--ttl", type=int, default=259200, help='live time of keys')
    parser.add_argument("-d", "--deamon", action='store_true', help='start as deamon mode')

    subparsers = parser.add_subparsers(help='sub-command help')
    parser_pipe = subparsers.add_parser("pipe", help="sync all file with pipelining")
    parser_pipe.set_defaults(func = pipe_sync_file)

    parser_tail = subparsers.add_parser("tail", help="sync once file grows")
    parser_tail.set_defaults(func = tail_sync_file)
    parser_tail.add_argument('-se', '--startfromend', action='store_true', help='start sync from the new appending rows')
 
    args = parser.parse_args()

    if args.deamon:
        try:
            #-- fork a child process, return 0 in the child and the child process id in the parent.
            #   see https://docs.python.org/2/library/os.html#os.fork
            pid = os.fork()

            #-- kill the current process if now is parent
            if 0 != pid:
                sys.exit(0)
        except OSError as e:
            logging.error(e, exc_info=True)
 
#    print args
    args.func(args)

 
