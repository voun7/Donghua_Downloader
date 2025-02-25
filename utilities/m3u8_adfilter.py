import logging
import re

logger = logging.getLogger(__name__)


class M3u8AdFilter:
    def __init__(self) -> None:
        self.response_text = None
        self.ads_removed, self.max_removed_ads, self.ad_max_duration = 0, 4, 30
        self.duration_tag, self.discon_tag = "#EXTINF:", "#EXT-X-DISCONTINUITY\n"

    def get_target_duration(self, tag: str = "#EXT-X-TARGETDURATION:") -> None | float | int:
        """
        Get the target duration of the video of the playlist.
        """
        dur_match = re.search(rf"{tag}(\d+\.?\d*)", self.response_text)
        if dur_match:
            dur_match = dur_match.group(1)
            target_dur = float(dur_match) if "." in dur_match else int(dur_match)
            return target_dur

    def get_discontinuities(self) -> list:
        """
        Get the discontinuity block from the response text.
        """
        discontinuities = self.response_text.split(self.discon_tag)
        return discontinuities[1:-1]  # Remove the header and footer of the playlist in the response text.

    def get_durations(self, text: str) -> list[float | int]:
        """
        Get the durations of the given text.
        """
        dur_match = re.findall(rf"{self.duration_tag}(\d+\.?\d*)", text)
        durations = [float(duration) if "." in duration else int(duration) for duration in dur_match]
        return durations

    def remove_single_discontinuity(self) -> None:
        """
        Remove a single discontinuity block from response text.
        :return:
        """

        def _sub(match: re.Match) -> str:
            logger.debug(f"Removing single pair discontinuity ad match: \n{match.group(0)}")
            return ""

        advert_pattern = re.compile(f"{self.discon_tag}(.*?){self.discon_tag}", re.DOTALL)
        result = advert_pattern.subn(_sub, self.response_text)
        self.response_text, self.ads_removed = result[0], self.ads_removed + result[1]

    def remove_double_discontinues(self) -> None:
        """
        Remove discontinuity blocks that have two tags at the start.
        """

        def _sub(match: re.Match) -> str:
            logger.debug(f"Removing double discontinuity ad match: \n{match.group(0)}")
            return ""

        advert_pattern = re.compile(f"{self.discon_tag}{self.discon_tag}(.*?){self.discon_tag}", re.DOTALL)
        result = advert_pattern.subn(_sub, self.response_text)
        self.response_text, self.ads_removed = result[0], self.ads_removed + result[1]

    def remove_suspicious_durations(self) -> None:
        """
        Remove response parts with suspicious durations that could be ads.
        """
        target_duration = self.get_target_duration()
        for discon in self.get_discontinuities():
            durations = self.get_durations(discon)
            if sum(durations) < self.ad_max_duration and sum(durations) % target_duration != 0:
                # The 2nd condition is for skipping discontinuity segments that all have the same duration as the
                # target length. Discontinuity with ads usually have varying length for its segments.
                logger.debug(f"Suspicious ad match: \n{discon}")
                self.response_text = self.response_text.replace(discon, "")
                self.ads_removed += 1

    def run_filters(self, response_text: str) -> str:
        """
        Run the methods in the class to remove ads from the response text.
        """
        self.response_text = response_text
        discon_len = len(self.get_discontinuities())
        if discon_len == 1:
            logger.debug(f"{discon_len} pair of discontinuity tags found.")
            self.remove_single_discontinuity()
        elif discon_len > 1:
            logger.debug(f"{discon_len} pairs of discontinuity tags found.")
            self.remove_double_discontinues()
            self.remove_suspicious_durations()
        else:
            logger.debug("No pair of discontinuity tags to remove ads found!")

        if self.ads_removed == 0:
            logger.debug(f"No advertisement found in the response text. Response text:\n{self.response_text}")
        elif self.ads_removed > self.max_removed_ads:  # The max number of parts that are allowed to be removed.
            logger.warning(f"Too many parts removed from playlist! Response text will be used instead.")
            self.response_text = response_text  # This is because some removed parts may not be ads.
        else:
            # Remove excess discontinuity tags remove response text.
            self.response_text = self.response_text.replace(f"{self.discon_tag}{self.discon_tag}", "")
        logger.debug(f"Number of ads removed: {self.ads_removed}")
        return self.response_text


if __name__ == '__main__':
    from pathlib import Path

    logging.basicConfig(level=logging.DEBUG, format="%(message)s")

    test_txt = Path("").read_text()
    af = M3u8AdFilter()
    res = af.run_filters(test_txt)
