import logging
import unittest

import psas_psarc
from psas_psarc._logging_classes import setup_loggers


class LoggingSetupTestCase(unittest.TestCase):
    def _reset_logger(self) -> logging.Logger:
        logger = logging.getLogger("psas_psarc")
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
        return logger

    def test_package_logger_is_quiet_by_default(self) -> None:
        logger = self._reset_logger()
        self.assertTrue(any(isinstance(handler, logging.NullHandler) for handler in logger.handlers))
        self.assertFalse(logger.propagate)

    def test_setup_loggers_uses_a_single_console_handler(self) -> None:
        logger = self._reset_logger()
        setup_loggers("psas_psarc", logging.INFO)

        self.assertEqual(len(logger.handlers), 1)
        self.assertTrue(any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers))
        self.assertFalse(logger.propagate)


if __name__ == "__main__":
    unittest.main()
