package com.venraas.msclient;

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
		Jedis jedis = _msclient.jedis();			
		return jedis.get(k);		
	}	
	
	@CrossOrigin
	@RequestMapping(value = "/status", method = RequestMethod.GET)
	public String status()
	{
		return "\"Good\"";
	}
	

}
