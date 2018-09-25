## Overview
![](https://drive.google.com/uc?id=1vpKtOSOKpR1yBDXW1_BWCxzfo2GX2U9h)

## Why we need [memorystore](https://cloud.google.com/memorystore/)


## Client

### [netcat](https://en.wikipedia.org/wiki/Netcat)
`nc -v ${HOST} ${PORT}`

### [redis-cli](https://redis.io/topics/rediscli)
* installation under Ubuntu  
  `apt-get install redis-tools`
  
`redis-cli -h ${HOST} -p 6379`

### [redis-py](https://github.com/andymccurdy/redis-py)

## Data type and commands
* [Redis keys](https://redis.io/topics/data-types-intro#redis-keys)

* [Strings](https://redis.io/topics/data-types#strings)
  * [SET key value](https://redis.io/commands/set)
  * [GET key](https://redis.io/commands/get)
  * [APPEND key value](https://redis.io/commands/append)
  
* [Lists](https://redis.io/topics/data-types#lists)
  * [LPUSH key value [value ...]](https://redis.io/commands/lpush)
  * [RPUSH key value [value ...]](https://redis.io/commands/rpush)
  * [LRANGE key start stop](https://redis.io/commands/lrange)
  * [LTRIM key start stop](https://redis.io/commands/ltrim)

## Reference
* [Cloud Memorystore](https://cloud.google.com/memorystore/)
* [Connecting to a Redis Instance from a Compute Engine VM](https://cloud.google.com/memorystore/docs/redis/connect-redis-instance-gce)

