import logging
import re
from itertools import chain
from pathlib import Path

from pycnnum import cn2num

logger = logging.getLogger(__name__)


class ChineseTitleGenerator:
    def __init__(self) -> None:
        self.name = None
        self.base_name = None
        self.suffixes = None
        self.filtered_name = None
        self.number_list = None

        # Regex patterns for name.
        self.all_number_pattern = re.compile(r'(\d+)')
        self.ep_range_pattern = re.compile(r'(?:第(\d+)[集季话])?.?第?(\d+)[-~](\d+)[集季话]')
        self.ch_keyword_pattern = re.compile(r'第(\d+)[集季话]')
        self.ch_num_pattern = re.compile(r'第([\u4e00-\u9fff]+)[集季话]')
        self.en_keyword_pattern = re.compile(r'[Ss](\d+)')
        self.ch_key_and_num_pattern = re.compile(r'季[-\d]')

    def set_suffixes(self) -> None:
        """
        If the string is a file path, remember its suffixes.
        """
        file_path = Path(self.name)
        if file_path.exists():
            self.suffixes = "".join(file_path.suffixes)
        else:
            self.suffixes = ""
        self.name = file_path.stem

    def filter_name(self) -> None:
        """
        Make the name easier for regex patterns to find relevant numbers.
        """
        self.filtered_name = self.name

        # change the chinese number in the name to regular numbers.
        if self.ch_num_pattern.search(self.filtered_name):
            logger.debug("ch_num_pattern match in name")
            chinese_numbers = self.ch_num_pattern.finditer(self.filtered_name)
            for match in chinese_numbers:
                ch_num_match = match.group(0)
                ch_num_in_english = str(cn2num(match.group(1)))
                self.filtered_name = self.filtered_name.replace(ch_num_match, f"第{ch_num_in_english}集")

        # replace the english keyword representing the season in the title with a chinese keyword.
        if self.en_keyword_pattern.search(self.filtered_name):
            logger.debug("en_keyword_pattern match in name")
            en_keyword = self.en_keyword_pattern.finditer(self.filtered_name)
            for match in en_keyword:
                en_char_match = match.group(0)
                logger.debug(f"en_char_match: {en_char_match}")
                en_char_match_num = match.group(1)
                self.filtered_name = self.filtered_name.replace(en_char_match, f"第{en_char_match_num}集")

        if self.ch_key_and_num_pattern.search(self.filtered_name):
            logger.debug("ch_key_and_num_pattern match in name")
            # removes chinese keyword prefix
            self.filtered_name = self.filtered_name.replace('第', '')

    def set_number_list(self) -> None:
        """
        Decides how the number list will be derived depending on the matching regex.
        """
        if self.ep_range_pattern.search(self.filtered_name):
            logger.debug("using ep_range_pattern numbers")
            result = self.ep_range_pattern.findall(self.filtered_name)
            self.number_list = list(filter(None, chain.from_iterable(result)))
        elif self.ch_keyword_pattern.search(self.filtered_name):
            logger.debug("using ch_keyword_pattern numbers")
            self.number_list = self.ch_keyword_pattern.findall(self.filtered_name)
        else:
            logger.debug("using all_number_pattern numbers")
            self.number_list = self.all_number_pattern.findall(self.filtered_name)

    def remove_leading_zeros(self) -> None:
        self.number_list = [ele.lstrip('0') for ele in self.number_list]

    def _set_ep_range_title(self) -> None:
        if len(self.number_list) == 2:
            first_ep_num = self.number_list[0]
            last_ep_num = self.number_list[1]
            self.name = f"{self.base_name} EP{first_ep_num}-{last_ep_num}{self.suffixes}"
        elif len(self.number_list) > 2:
            season_num = self.number_list[0]
            first_ep_num = self.number_list[1]
            last_ep_num = self.number_list[2]
            self.name = f"{self.base_name} S{season_num} EP{first_ep_num}-{last_ep_num}{self.suffixes}"

    def set_title(self) -> None:
        if self.ep_range_pattern.search(self.filtered_name):
            self._set_ep_range_title()
            return

        if len(self.number_list) == 1:
            ep_num = self.number_list[0]
            self.name = f"{self.base_name} EP{ep_num}{self.suffixes}"
        elif len(self.number_list) > 1:
            season_num = self.number_list[0]
            episode_num = self.number_list[1]
            self.name = f"{self.base_name} S{season_num} EP{episode_num}{self.suffixes}"

    def generate_title(self, name: str, base_name: str) -> str:
        """
        Runs the title generation process.
        :param name: the name or file path of the title.
        :param base_name: the name that will be used as the foundation for new title generated
        :return: a new generated title.
        """
        logger.debug(f"Initial name: {name}")
        self.name = name
        self.base_name = base_name
        self.set_suffixes()
        logger.debug(f"suffixes: {self.suffixes}")
        self.filter_name()
        logger.debug(f"filtered name: {self.filtered_name}")
        self.set_number_list()
        logger.debug(f"number list: {self.number_list}")
        self.remove_leading_zeros()
        logger.debug(f"leading zeros removed: {self.number_list}")
        self.set_title()
        return self.name
