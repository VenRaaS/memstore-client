import os, sys, time 
import logging
import argparse
import json
import threading
from multiprocessing import Pool, Value
import requests



logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %I:%M:%S')
logging.getLogger("requests").setLevel(logging.WARNING)

es_host = '10.140.0.5'
reqsess = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_maxsize=512)
reqsess.mount('http://{h}:9200'.format(h=es_host), adapter)

#TODO paramtize expire_sec_mpv
expire_sec_mpv = Value('i', 0)


def es_get(dic):
    global reqsess

    rt = None
    try:
        url = 'http://{h}:9200/{c}_mod/{t}/_search?q=gid:{i}'.format(h=es_host, c=dic['code_name'], t=dic['table_name'], i=dic['gid'])
        rt = reqsess.get(url)

#        print rt.status_code
    except Exception as e:
        logging.error(e, exc_info=True)

    return rt


def es_post(dic):
    global reqsess

    try:
        url = 'http://{h}:9200/{c}_mod/{t}'.format(h=es_host, c=dic['code_name'], t=dic['table_name'])
        dic.pop('code_name')
        dic.pop('table_name')

        r = reqsess.post(url, json=dic)
#        print r.status_code
#        print r.text
    except Exception as e:
        logging.error(e, exc_info=True)


def batch_sync_file(args) :
    jkey_c = args.c 
    jkey_t = args.t
    jkey_i = args.i
    jkey_v = args.v
    logging.info('combo key: ${0}.${1}.${2}'.format(jkey_c, jkey_t, jkey_i))
    logging.info('value key: {0}'.format(jkey_v))
    logging.info('ttl: {0}'.format(args.ttl))
    logging.info('command: {0}'.format(args.cmd_es))
    if args.ttl: 
        expire_sec_mpv.value = args.ttl

    logging.info('{} counting ...'.format(args.src_fp))
    size_src = 0.0
    with open(args.src_fp, 'r') as f:
        for i, l in enumerate(f):
            size_src = i
            pass
    size_src += 1.0
    logging.info('{} has {:.0f} records'.format(args.src_fp, size_src))

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

            dic = { jkey_c:j[jkey_c], jkey_t:j[jkey_t], jkey_i:j[jkey_i], jkey_v:j[jkey_v] }
            vals.append(dic)
    
            if i_line % 30000 == 0:
                if ESCommand.post == args.cmd_es:
                    pool.map(es_post, vals)
                elif ESCommand.get == args.cmd_es:
                    pool.map(es_get, vals)

                keys = []
                vals = []

                logging.info('{:.0f} {:.0f}%'.format(i_line, i_line / size_src * 100))
            
        if ESCommand.post == args.cmd_es:
            pool.map(es_post, vals)
        elif ESCommand.get == args.cmd_es:
            pool.map(es_get, vals)

    logging.info('{:.0f} {:.0f}%'.format(size_src, 100.0))


from enum import Enum
class ESCommand(Enum):
    post = 'post'
    get = 'get'

    def __str__(self):
        return self.value


if '__main__' == __name__:
    parser = argparse.ArgumentParser()
    parser.add_argument("src_fp", help="source file path")
    subparsers = parser.add_subparsers(help='sub-command help')

    jkey_c = 'code_name'
    jkey_t = 'table_name'
    jkey_i = 'id'
    jkey_v = 'indicators_raw'
    parser_bat = subparsers.add_parser("batch", help="sync file all at once")
    parser_bat.add_argument('cmd_es', type=ESCommand, choices=list(ESCommand), help="es commands")
    parser_bat.add_argument("-c", default="{0}".format(jkey_c), help="source json key represents code name, default: {0}".format(jkey_c))
    parser_bat.add_argument("-t", default="{0}".format(jkey_t), help="source json key represents table/mode name, default: {0}".format(jkey_t))
    parser_bat.add_argument("-i", default="{0}".format(jkey_i), help="source json key represents gid/category/item/rule id, default: {0}".format(jkey_i))
    parser_bat.add_argument("-v", default="{0}".format(jkey_v), help="source json key represents rule/recomd list, default: {0}".format(jkey_v))
    parser_bat.add_argument("-ttl", type=int, help='live time of keys')
    parser_bat.set_defaults(func = batch_sync_file)

    args = parser.parse_args()
    args.func(args)

 
