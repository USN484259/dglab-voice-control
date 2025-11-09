#!/usr/bin/env python3

import os
import sys
import json
import logging

from sounddevice import RawInputStream
from vosk import Model, KaldiRecognizer, SetLogLevel

logger = logging.getLogger("transcriber")

class VoskTranscriber:
	def __init__(self, config, handler):
		self.audio_src = RawInputStream(channels = 1, dtype = "int16", device = config.get("device"), callback = self.audio_callback)
		logger.info("device %s, samplerate %d", self.audio_src.device, self.audio_src.samplerate)
		self.model = Model(config.get("model"))
		logger.info("loaded model %s", config.get("model"))
		self.recognizer = KaldiRecognizer(self.model, self.audio_src.samplerate)
		self.handler = handler

	def start(self):
		self.audio_src.start()

	def close(self):
		self.audio_src.stop()
		result = json.loads(self.recognizer.FinalResult())
		self.handler(result.get("text", ""))
		self.audio.close()

	def audio_callback(self, indata, frames, time, status):
		data = bytes(indata)

		result = None
		if self.recognizer.AcceptWaveform(data):
			result = json.loads(self.recognizer.Result())
			logger.debug(result)
			self.handler(result.get("text", ""))
		# else:
		# 	result = self.recognizer.PartialResult()
		# print(result)


