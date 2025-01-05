#!/usr/bin/env python3

from pathlib import Path
from typing import List, Optional
import logging

import requests
from fire import Fire

import pandas as pd
from bibtexparser.bparser import BibTexParser
from pylatexenc.latexwalker import LatexWalker, LatexEnvironmentNode, LatexMacroNode, LatexCharsNode, LatexCommentNode


def get_cites(tex_content: str) -> List[str]:
    """
    tex_content: string containing tex
    return: list of cited references
    """

    w = LatexWalker(tex_content)
    (nodelist, pos, len_) = w.get_latex_nodes(pos=0)

    cites = []
    for node in nodelist:
        if isinstance(node, LatexMacroNode) and node.macroname=="cite":
            args = node.nodeargd.argnlist[3].nodelist
            for arg in args:
                if isinstance(arg, LatexCharsNode) and not isinstance(arg, LatexCommentNode):
                    for cite in arg.chars.strip().split(","):
                        cites.append(cite.strip())

    cites = [cite for cite in cites if cite != ""]
    return cites


def get_all_cites_in_dir(dir_: str) -> List[str]:
    """
    Searches for all .tex files in `dir_` and extracts all cites.

    dir_: path to directory containing .tex files
    return: list of cited references
    """
    cites = []
    all_tex_files = list(Path(dir_).rglob("*.tex"))

    for tex_file_name in all_tex_files:
        with open(tex_file_name) as file_:
            tex_content = file_.read()
        cites.extend(get_cites(tex_content))

    cites = list(set(cites))
    return cites


def bibtex_to_df(bibtex_file: str, *, verify_urls=False) -> pd.DataFrame:
    """
    Convert bibtex file to table.

    bibtex_file: path to bibtex file
    return: pandas DataFrame
    """

    bp = BibTexParser(interpolate_strings=False, ignore_nonstandard_types=False)

    with open(bibtex_file, encoding="utf8") as related_file:
        bib_database = bp.parse_file(related_file)
        bib_df = pd.DataFrame(bib_database.entries)

    if verify_urls:
        logging.info("Verifing URLs")
        bib_df["url_response"] = bib_df["url"].dropna().apply(requests.get)
        bib_df["url_response_status"] = bib_df["url_response"].dropna().apply(lambda x: x.status_code)
        bib_df["url_response_content"] = bib_df["url_response"].dropna().apply(lambda x: x._content)

    # -- Reorder cols
    front_cols = ["ID", "ENTRYTYPE", "title", "author", "booktitle", "journal", "year"]
    if set(front_cols).issubset(bib_df.columns):
        other_cols = [col for col in bib_df.columns if col not in front_cols]
        bib_df = bib_df[front_cols + other_cols]
    else:
        logging.info("Could not reorder columns")

    return bib_df


def merge_cites_in_dir_with_bibtex(
    bib_file: Optional[str] = None,
    dir_: Optional[str] = None,
    verify_urls: bool = False,
    drop_cols: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Collects information about latex citations from a all .tex files in a directory and a bibtex file into one table.

    :dir_: path to directory where I will search for .tex files
    :bib_file: path to bibtex file
    :verify_urls: sends an http request to each url in the `bib_file` and reports return status code and message via new columns
    :drop_cols: list of columns to drop

    :returns: pandas DataFrame containing all information from `bib_file`. Append commands to view the dataframe, e.g. `to_csv`

    EXAMPLE usage in combination with visidata:

        `bibtex_utils DIR BIBTEX_FILE to_csv | vd --filetype=csv`
    """

    logging.info("Extracting cites")
    if dir_ is not None:
        cites_df = pd.DataFrame({"ID": get_all_cites_in_dir(dir_)})
        cites_df["cited"] = True
    else:
        cites_df = pd.DataFrame(columns=["ID"])
    cites_df["ID"] = cites_df["ID"].astype(object)

    logging.info("Loading bibtex database")
    if bib_file is not None:
        bib_df = bibtex_to_df(bib_file, verify_urls=verify_urls)
    else:
        bib_df = pd.DataFrame(columns=["ID"])

    logging.info("Merging cites and bibtex-database")
    merged_df = cites_df.merge(bib_df, on="ID", how="outer")

    if "cited" in merged_df.columns:
        merged_df["cited"] = merged_df["cited"].fillna(False)

    if drop_cols is not None:
        merged_df = merged_df.drop(columns=drop_cols)

    return merged_df


def cli(
    bib_file: Optional[str] = None,
    dir_: Optional[str] = None,
    verify_urls=False,
    drop_cols: Optional[List[str]] = None
) -> str:
    """
    Collects information about latex citations from (1) all .tex files in a directory and
    (2) a bibtex file, and puts them into one table.

    :dir_: path to directory where to search for .tex files and citations inside them
    :bib_file: path to bibtex file
    :verify_urls: sends an http request to each url in the `bib_file` and reports return status code and message via new columns
    :drop_cols: comma-separated list of columns to drop

    :returns: table in CSV format containing all information from `bib_file`.

    EXAMPLE usage in combination with visidata:

        `bibtex_utils BIBTEX_FILE DIR | vd --filetype=csv`
    """
    # in some cases, fire make drop_cols a tuple, which causes issues down the line
    if drop_cols is not None:
        drop_cols = list(drop_cols)
    return merge_cites_in_dir_with_bibtex(bib_file, dir_, verify_urls, drop_cols).to_csv(index=False)
#
#
# if __name__ == "__main__":
#     Fire(cli)
