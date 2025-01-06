#!/usr/bin/env python3

from pathlib import Path
from typing import List, Optional, Set, Callable
import logging
import re

import requests
from fire import Fire

import pandas as pd
from bibtexparser.bparser import BibTexParser


def extract_citation_ids(latex_content: str) -> Set[str]:
    # Split the content into lines
    lines = latex_content.split('\n')

    # Define the regex pattern for capturing LaTeX citation IDs
    pattern = r'\\cite\{([^}]+)\}'

    citation_ids: Set[str] = set()

    for line in lines:
        # Remove inline comments
        line = re.sub(r'(?<!\\)%.*', '', line)

        matches = re.findall(pattern, line)

        # Split the matched citation keys by comma and add them to the set
        for match in matches:
            citation_ids = citation_ids.union({item.strip() for item in match.split(',')})

    return citation_ids


def get_all_cites_in_dir(tex_dir: str) -> Set[str]:
    """Search for all .tex files in `tex_dir` and extracts all cites.

    tex_dir: path to directory containing .tex files
    return: list of cited references
    """
    all_cites: Set[str] = set()
    all_tex_files = list(Path(tex_dir).rglob("*.tex"))

    for tex_file_name in all_tex_files:
        with open(tex_file_name) as file_:
            tex_content = file_.read()
        cites = extract_citation_ids(tex_content)
        all_cites = all_cites.union(cites)

    return all_cites


def bib_to_df(bibtex_file: str, *, verify_urls=False) -> pd.DataFrame:
    """Convert bibtex file to table.

    bibtex_file: path to bibtex file
    return: pandas DataFrame
    """
    bp = BibTexParser(interpolate_strings=False, ignore_nonstandard_types=False)

    with open(bibtex_file, encoding="utf8") as related_file:
        bib_database = bp.parse_file(related_file)
        bib_df = pd.DataFrame(bib_database.entries)

    if verify_urls:
        logging.info("Verifing URLs")
        requests_get: Callable = requests.get
        bib_df["url_response"] = bib_df["url"].dropna().apply(requests_get)
        bib_df["url_response_status"] = (
            bib_df["url_response"].dropna().apply(lambda x: x.status_code)
        )
        bib_df["url_response_content"] = bib_df["url_response"].dropna().apply(lambda x: x._content)

    # -- Reorder cols
    front_cols = ["ID", "ENTRYTYPE", "title", "author", "booktitle", "journal", "year"]
    if set(front_cols).issubset(bib_df.columns):
        other_cols = [col for col in bib_df.columns if col not in front_cols]
        bib_df = bib_df[front_cols + other_cols]
    else:
        logging.info("Could not reorder columns")

    return bib_df


def merge_bib_and_cites(bibtex_df: pd.DataFrame, cites: List[str]) -> pd.DataFrame:
    """ """
    cites_df = pd.DataFrame({"ID": cites})
    cites_df["cited"] = True
    cites_df["ID"] = cites_df["ID"].astype(object)
    merged_df = cites_df.merge(bibtex_df, on="ID", how="outer")
    merged_df["cited"] = merged_df["cited"].fillna(False)

    return merged_df


def bib_to_csv(
    bib_file: str,
    tex_dir: Optional[str] = None,
    verify_urls=False,
    drop_cols: Optional[List[str]] = None,
) -> str:
    """Convert .bib file to csv. Optionally include citations from .tex files in a `tex_dir`.

    :bib_file: path to bibtex file
    :tex_dir: path to directory containing .tex files with citations
    :verify_urls: sends http requests urls mentioned in `bib_file` and report return code and message
    :drop_cols: list of columns to drop

    :returns: table in CSV format containing all information from `bib_file`.

    EXAMPLE usage in combination with visidata:

        `bibtex_utils BIBTEX_FILE DIR | vd --filetype=csv`
    """
    bib_df = bib_to_df(bib_file, verify_urls=verify_urls)

    if drop_cols is not None:
        # in some cases, fire make drop_cols a tuple, which causes issues down the line
        drop_cols = list(drop_cols)
        bib_df = bib_df.drop(columns=drop_cols)

    if tex_dir is not None:
        cites = list(get_all_cites_in_dir(tex_dir))
        df = merge_bib_and_cites(bib_df, cites)
    else:
        df = bib_df

    return df.to_csv(index=False)


def main():
    exposed_functions = [bib_to_csv, get_all_cites_in_dir]
    Fire({func.__name__: func for func in exposed_functions})
