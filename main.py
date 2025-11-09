#!/usr/bin/env python3

import os
import sys
import json
import asyncio
import logging
import argparse

if sys.hexversion >= 0x030B0000:
	import tomllib as toml
	toml_open_flag = "rb"
else:
	import toml
	toml_open_flag = "r"

from sounddevice import query_devices
from transcriber import VoskTranscriber
from controller import DglabController
from webserver import DglabWebServer

LOG_FORMAT = "%(asctime)s\t%(levelname)s\t%(name)s\t%(message)s"

logger = logging.getLogger("main")


def main(args):
	with open(args.config, toml_open_flag) as f:
		config = toml.load(f)

	server = DglabWebServer(config.get("server"))
	controller = DglabController(server, config.get("wave"), config.get("rules"))
	transcriber = VoskTranscriber(config.get("transcriber"), controller.feed)

	async def startup_handler():
		logger.info("starting")
		await controller.start()
		transcriber.start()
		return controller.handle_msg

	server.run(startup_handler)


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("-v", "--verbose", action = "store_true")
	parser.add_argument("config", nargs = '?')

	args = parser.parse_args()

	logging.basicConfig(level = args.verbose and logging.DEBUG or logging.INFO, format = LOG_FORMAT)

	if not args.config:
		print(query_devices())
	else:
		main(args)