#!/usr/bin/env python3

import re
import math
import json
import asyncio
import logging
from asyncio import CancelledError
from contextlib import suppress

logger = logging.getLogger("controller")

strength_feedback_pattern = re.compile(r"strength-(\d+)[+](\d+)[+](\d+)[+](\d+)")
builtin_wave = ["0A0A0A0A64646464"]


def merge_pulse(current, rec, ts):
	if current is None:
		return rec
	elif rec is None:
		return current

	if current["strength"] < rec["strength"]:
		return rec
	else:
		return current


class DglabController:
	# public
	def __init__(self, server, wave_map, rules):
		self.interval = 100
		self.server = server
		self.wave_map = wave_map or {}
		self.rules = rules or {}
		self.loop = None
		self.queue = None
		self.match_task = None
		self.pulse_task = {
			'A': None,
			'B': None,
		}
		self.lock = asyncio.Lock()
		self.pulse_list = {
			'A': [],
			'B': [],
		}
		self.limit = {
			'A': 0,
			'B': 0,
		}

	async def start(self):
		self.loop = asyncio.get_running_loop()
		self.queue = asyncio.Queue(0x10)
		self.match_task = asyncio.create_task(self.match_func())
		self.match_task.add_done_callback(asyncio.Task.result)

	async def close(self):
		if self.match_task is not None:
			with suppress(CancelledError):
				self.match_task.cancel()
			self.match_task = None

		if self.pulse_task is not None:
			with suppress(CancelledError):
				self.pulse_task.cancel()
			self.pulse_task = None

		await self.server.feed_control("strength-1+2+0")
		await self.server.feed_control("strength-2+2+0")

	async def handle_msg(self, text):
		match = strength_feedback_pattern.fullmatch(text)
		if match:
			async with self.lock:
				self.limit['A'] = int(match[3])
				self.limit['B'] = int(match[4])


	def feed(self, text):
		future = asyncio.run_coroutine_threadsafe(self.queue.put(text), self.loop)
		future.result()

	# private
	async def match_func(self):
		while True:
			text = await self.queue.get()
			text = text.replace(' ', '')
			if not text:
				continue
			logger.debug("got\t%s", text)
			await self.server.feed_log(text)
			for name, rule in self.rules.items():
				found = False
				for pattern in rule["match"]:
					if pattern in text:
						found = True
						break
				if found:
					async with self.lock:
						for channel in ('A', 'B'):
							obj = rule.get(channel)
							if obj is None:
								continue
							rec = {
								"name": "%s-%s" % (str(name), channel),
								"time": 0,
								"duration": obj.get("duration") or rule.get("duration", 0),
								"wave": obj.get("wave", "default"),
								"strength": obj.get("strength", 100),
							}
							logger.info("trigger %s, %d", rec["name"], rec["duration"])
							self.pulse_list[channel].append(rec)
							if not self.pulse_task[channel]:
								task = asyncio.create_task(self.pulse_func(channel))
								task.add_done_callback(asyncio.Task.result)
								self.pulse_task[channel] = task


	async def pulse_func(self, channel):
		channel_num = chr(ord(channel) - 0x10)
		logger.debug("pulse_func %s enter", channel)
		initial = True
		prev_strength = 0
		prev_wave = None
		wave_data = None
		wave_index = 0
		while True:
			pulse = None
			async with self.lock:
				if not self.pulse_list[channel]:
					logger.debug("pulse_func %s exit", channel)
					try:
						await self.server.feed_control("clear-" + channel_num)
						await self.server.feed_control("strength-%s+2+0" % channel_num)
					finally:
						self.pulse_task[channel] = None
					return

				new_list = []
				for rec in self.pulse_list[channel]:
					ts = rec["time"]
					rec["time"] += (not initial) and self.interval or 0
					pulse = merge_pulse(pulse, rec, ts)

					if rec["time"] < rec["duration"]:
						new_list.append(rec)
					else:
						logger.info("expire %s, %d", rec["name"], rec["duration"])
				self.pulse_list[channel] = new_list

			if pulse:
				strength = self.limit[channel] * pulse["strength"] // 100
				if prev_strength != strength:
					logger.info("channel %s: %d", channel, strength)
					await self.server.feed_control("strength-%s+2+%d" % (channel_num, strength))

				wave_name = pulse["wave"]
				if (not prev_wave) or prev_wave != wave_name:
					wave_data = self.wave_map.get(wave_name, builtin_wave)
					wave_index = 0
					prev_wave = wave_name
					prev_strength = strength


				assert(self.interval == 100)
				step = 1 + initial
				while step > 0:
					await self.server.feed_control("pulse-%s:" % channel + json.dumps(wave_data[wave_index:(wave_index+1)]))
					wave_index = (wave_index + 1) % len(wave_data)
					step -= 1

			await asyncio.sleep(self.interval / 1000)
			initial = False
