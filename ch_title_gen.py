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
        self.range_pattern = re.compile(r'\d+[-~]\d+')
        # Regex for english characters.
        self.en_key_ch_key_pattern = re.compile(r'[Ss](\d+)')
        self.en_key_season_ep_pattern = re.compile(r'(?:[Ss](\d+).*)?(?:E|EP|ep)(\d+)')
        # Regex for chinese characters.
        self.ch_key_and_num_pattern = re.compile(r'[集季][-\d]')  # Consider removing, not need for most cases.
        self.ch_keyword_pattern = re.compile(r'第(\d+)[集季话]')
        self.ch_num_pattern = re.compile(r'第([\u4e00-\u9fff]+)[集季话]')
        self.ch_key_range_pattern = re.compile(r'(?:第(\d+)[集季话].*)?第(\d+)[-~](\d+)[集季话]')

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

    def miscellaneous_strings_filter(self) -> None:
        """
        Remove common strings from name that may lead to incorrect generated name.
        """
        miscellaneous_strings = ["1080P", "4K"]
        for char in miscellaneous_strings:
            if char in self.filtered_name:
                self.filtered_name = self.filtered_name.replace(char, '')

    def chinese_num_filter(self) -> None:
        """
        Change the chinese number in the name to regular numbers.
        """
        if self.ch_num_pattern.search(self.filtered_name):
            logger.debug("ch_num_pattern match in name")
            matches = self.ch_num_pattern.finditer(self.filtered_name)
            for match in matches:
                ch_num_match = match.group(0)
                ch_num_in_english = str(cn2num(match.group(1)))
                self.filtered_name = self.filtered_name.replace(ch_num_match, f"第{ch_num_in_english}集")

    def en_key_ch_key_filter(self) -> None:
        """
        Replace the english keyword representing the season in the title with a chinese keyword.
        Only works on names that have season keyword in english but no episode keyword.
        """
        if self.en_key_ch_key_pattern.search(self.filtered_name):
            logger.debug("en_key_ch_key_pattern match in name")
            matches = self.en_key_ch_key_pattern.finditer(self.filtered_name)
            for match in matches:
                en_char_match = match.group(0)
                logger.debug(f"en_char_match: {en_char_match}")
                en_char_match_num = match.group(1)
                self.filtered_name = self.filtered_name.replace(en_char_match, f"第{en_char_match_num}集")

    def filter_name(self) -> None:
        """
        Make the name easier for regex patterns to find relevant numbers.
        """
        self.filtered_name = self.name

        self.miscellaneous_strings_filter()
        self.chinese_num_filter()
        self.en_key_ch_key_filter()

        if self.ch_key_and_num_pattern.search(self.filtered_name):
            logger.debug("ch_key_and_num_pattern match in name")
            # Removes chinese keyword prefix to allow all numbers to be captured instead.
            self.filtered_name = self.filtered_name.replace('第', '')

    def set_number_list(self) -> None:
        """
        Decides how the number list will be derived depending on the matching regex.
        """
        if self.ch_key_range_pattern.search(self.filtered_name):
            logger.debug("using ch_key_range_pattern numbers")
            captured_groups = self.ch_key_range_pattern.findall(self.filtered_name)
            self.number_list = list(filter(None, chain.from_iterable(captured_groups)))
        elif self.range_pattern.search(self.filtered_name):
            logger.debug("using range_pattern numbers")
            self.number_list = self.all_number_pattern.findall(self.filtered_name)
        elif self.ch_keyword_pattern.search(self.filtered_name):
            logger.debug("using ch_keyword_pattern numbers")
            self.number_list = self.ch_keyword_pattern.findall(self.filtered_name)
        elif self.en_key_season_ep_pattern.search(self.name):
            logger.debug("using en_key_season_ep_pattern numbers")
            captured_groups = self.en_key_season_ep_pattern.findall(self.name)
            self.number_list = list(filter(None, chain.from_iterable(captured_groups)))
        else:
            logger.debug("using all_number_pattern numbers")
            self.number_list = self.all_number_pattern.findall(self.filtered_name)

    def remove_leading_zeros(self) -> None:
        """
        Remove leading zeros from name to increase consistency in generated names.
        """
        self.number_list = [ele.lstrip('0') for ele in self.number_list]

    def _set_ep_range_title(self) -> None:
        """
        Use the numbers in the number list and base name to build a new name for names with range in them.
        """
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
        """
        Use the numbers in the number list and base name to build a new name.
        """
        if len(self.number_list) == 0:
            logger.debug(f"{self.name} has no numbers")
            self.name = f"{self.name}{self.suffixes}"
            return

        if self.range_pattern.search(self.filtered_name):
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
        :param name: The name or file path of the title.
        :param base_name: The name that will be used as the foundation for new title generated.
        :return: A new generated title or same name if no numbers found.
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


if __name__ == '__main__':
    # Change debug logs to print when testing.
    test_folder = Path(r"")
    gen = ChineseTitleGenerator()
    for file in test_folder.iterdir():
        new_name = gen.generate_title(str(file), "base name")
        print(f"New Name: {new_name}\n")
