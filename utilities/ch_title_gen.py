import logging
import re
from itertools import chain
from pathlib import Path

from pycnnum import cn2num

logger = logging.getLogger(__name__)


class ChineseTitleGenerator:
    def __init__(self) -> None:
        self.name = self.base_name = self.suffixes = self.filtered_name = None
        self.season_no = self.episode_range_no = self.episode_no = None

        # Regex patterns for name.
        self.all_numbers_pattern = re.compile(r'(\d+)')
        self.ch_num_pattern = re.compile(r'第([零一二三四五六七八九十百千万]+)[集季话]')
        self.season_pattern = re.compile(r'第?\s*(\d+)季|(?:Season|S)\s*(\d+)')
        self.episode_range_pattern = re.compile(r'(\d+)\s*[-~～]\s*(\d+)')
        self.episode_pattern = re.compile(r'[第季]\s*(\d+)[集话]|(?:Episode|EP|E)\s*(\d+)')

    def get_suffixes(self) -> str:
        """
        If the string is a file path, remember its suffixes and set the name to a name without the suffixes in it.
        """
        file_path = Path(self.name)
        if file_path.exists():
            filtered_suffixes = [suffix for suffix in file_path.suffixes if " " not in suffix and len(suffix) < 8]
            self.name = file_path.stem
            suffixes = "".join(filtered_suffixes)
            logger.debug(f"name: {self.name}. suffixes: {suffixes}")
            return suffixes
        else:
            logger.debug(f"name: {self.name}")
            return ""

    @staticmethod
    def miscellaneous_strings_filter(name: str) -> str:
        """
        Remove common strings from name that may lead to incorrect generated name.
        """
        miscellaneous_strings = ["1080P", "4K"]
        for char in miscellaneous_strings:
            if char in name:
                logger.debug(f"miscellaneous_string: {char}, removed from: {name}")
                name = name.replace(char, '')
        return name

    def chinese_num_filter(self, name: str) -> str:
        """
        Change the chinese number in the name to regular numbers.
        """
        if self.ch_num_pattern.search(name):
            logger.debug("ch_num_pattern match in name")
            matches = self.ch_num_pattern.finditer(name)
            for match in matches:
                ch_num_match, ch_num, ch_num_index = match.group(0), match.group(1), match.span(1)
                logger.debug(f"ch_num_match found: {ch_num_match}, ch_num found: {ch_num}")
                ch_num_in_english = str(cn2num(ch_num))
                name = name[:ch_num_index[0]] + ch_num_in_english + name[ch_num_index[1]:]
            logger.debug(f"ch_num filtered name: {name}")
        return name

    def get_filtered_name(self, name: str) -> str:
        """
        Make the name easier for regex patterns to find relevant numbers.
        """
        filtered_name = self.miscellaneous_strings_filter(name)
        filtered_name = self.chinese_num_filter(filtered_name)
        return filtered_name

    def use_all_name_numbers(self) -> None:
        """
        Use all the numbers in the name to set the season number and episode number.
        """
        logger.debug("using all_numbers_pattern numbers")
        number_list = self.all_numbers_pattern.findall(self.filtered_name)
        number_list_length = len(number_list)
        if number_list_length == 1:
            self.episode_no = number_list[0]
        elif number_list_length >= 2:
            self.season_no, self.episode_no = number_list[0], number_list[1]

    def get_title_numbers(self) -> None:
        """
        Uses the numbers in the title to set the season, episode and episode range numbers.
        """
        season_match = self.season_pattern.search(self.filtered_name)
        logger.debug(f"season_match: {season_match}")
        if season_match:
            self.season_no = next(match for match in season_match.groups() if match is not None)
        episode_range_match = self.episode_range_pattern.search(self.filtered_name)
        logger.debug(f"episode_range_match: {episode_range_match}")
        if episode_range_match:
            self.episode_range_no = episode_range_match.groups()
        else:
            episode_match = self.episode_pattern.search(self.filtered_name)
            logger.debug(f"episode_match: {episode_match}")
            if episode_match:
                self.episode_no = next(match for match in episode_match.groups() if match is not None)
            else:
                # This condition is used when the season number tag is used for the episode number.
                season_result = self.season_pattern.findall(self.filtered_name)
                season_matches = list(filter(None, chain.from_iterable(season_result)))
                if len(season_matches) > 1 and season_matches[0] != season_matches[1]:
                    logger.debug("Using season_matches to find episode_no")
                    self.episode_no = season_matches[1]

        if self.episode_range_no is None and self.episode_no is None:
            self.use_all_name_numbers()

        logger.debug(f"season_no: {self.season_no}, "
                     f"episode_range_no: {self.episode_range_no}, "
                     f"episode_no: {self.episode_no}")

    def remove_leading_zeros(self) -> None:
        """
        Remove any leading zeros from name to increase consistency in generated names.
        """
        if self.season_no and self.season_no.startswith('0'):
            self.season_no = self.season_no.lstrip('0')
            logger.debug(f"leading zeros removed: S:{self.season_no}")
        if self.episode_range_no and self.episode_range_no[0].startswith('0'):
            self.episode_range_no = (self.episode_range_no[0].lstrip('0'), self.episode_range_no[1].lstrip('0'))
            logger.debug(f"leading zeros removed: EP_range:{self.episode_range_no}")
        if self.episode_no and self.episode_no.startswith('0'):
            self.episode_no = self.episode_no.lstrip('0')
            logger.debug(f"leading zeros removed: EP:{self.episode_no}")

    def _set_ep_range_title(self) -> None:
        """
        Use the numbers in the number list and base name to build a new name for names with range in them.
        """
        first_ep_num = self.episode_range_no[0]
        last_ep_num = self.episode_range_no[1]
        if self.season_no and self.episode_range_no:
            self.name = f"{self.base_name} S{self.season_no} EP{first_ep_num}-{last_ep_num}{self.suffixes}"
        elif self.episode_range_no:
            self.name = f"{self.base_name} EP{first_ep_num}-{last_ep_num}{self.suffixes}"

    def set_title(self) -> None:
        """
        Use the numbers in the number list and base name to build a new name.
        """
        if self.episode_range_pattern.search(self.filtered_name):
            self._set_ep_range_title()
            return

        if self.season_no and self.episode_no:
            self.name = f"{self.base_name} S{self.season_no} EP{self.episode_no}{self.suffixes}"
        elif self.episode_no:
            self.name = f"{self.base_name} EP{self.episode_no}{self.suffixes}"
        elif self.season_no:
            self.name = f"{self.base_name} S{self.season_no}{self.suffixes}"

    def title_final_filter(self) -> None:
        """
        Add finishing touches to generated name after it has been set.
        """
        if "S1 " in self.name:  # For cases were the first season indicator is included. For uniformity in gen names.
            logger.debug("removing S1 tag from title")
            self.name = self.name.replace("S1 ", "")

    def generate_title(self, name: str, base_name: str) -> str:
        """
        Runs the title generation process.
        :param name: The name or file path of the title.
        :param base_name: The name that will be used as the foundation for new title generated.
        :return: A new generated title or same name if no numbers found.
        """
        self.name, self.base_name = name, base_name
        self.season_no = self.episode_range_no = self.episode_no = None  # Clear previous values from memory.
        self.suffixes = self.get_suffixes()
        self.filtered_name = self.get_filtered_name(self.name)
        self.get_title_numbers()
        self.remove_leading_zeros()
        self.set_title()
        self.title_final_filter()
        return self.name


if __name__ == '__main__':
    # Change debug logs to print when testing.
    test_folder = Path(r"")
    gen = ChineseTitleGenerator()
    for file in test_folder.iterdir():
        new_name = gen.generate_title(str(file), "base name")
        logger.debug(f"New Name: {new_name}\n")
