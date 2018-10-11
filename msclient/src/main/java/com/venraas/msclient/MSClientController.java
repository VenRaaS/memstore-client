package com.venraas.msclient;

import java.util.ArrayList;
import java.util.List;

import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;

import redis.clients.jedis.Jedis;


@RestController
@RequestMapping("/api")
public class MSClientController {
	
	MSClient _msclient = MSClient.getInstance();
	
	
	@CrossOrigin
	@RequestMapping(value = "/rule", method = RequestMethod.GET)
	public String rule(String k){		
		List<String> l = new ArrayList<String>();
		
		//-- try-with-resource
		//   https://github.com/xetorthio/jedis/wiki/Getting-started#basic-usage-example
		try (Jedis jedis = _msclient.jedis()){
			l = jedis.lrange(k, 0, -1);
		}		
		
		return (0 < l.size()) ? l.get(0): "";		
	}	
	
	@CrossOrigin
	@RequestMapping(value = "/status", method = RequestMethod.GET)
	public String status()
	{
		return "\"Good\"";
	}
	

}
