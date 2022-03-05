import json
import logging
import os
import time

import requests
from tqdm import tqdm

from pygetpapers.download_tools import DownloadTools
from pygetpapers.pgexceptions import PygetpapersError

TOTAL_HITS = "total_hits"
NEW_RESULTS = "new_results"
RXIV_RESULT = "rxiv_result"
UPDATED_DICT = "updated_dict"
JATSXML = "jatsxml"
FULLTEXT_XML = "fulltext.xml"
DOI = "doi"
TOTAL_JSON_OUTPUT = "total_json_output"
BIORXIV = "biorxiv"
MESSAGES = "messages"
TOTAL = "total"
COLLECTION = "collection"
CURSOR_MARK = "cursor_mark"
RXIV = "rxiv"


class Rxiv:
    """Rxiv class which handles Biorxiv and Medrxiv repository"""

    def __init__(self,api="biorxiv"):
        """initiate Rxiv class"""
        self.download_tools = DownloadTools(api)
        self.get_url = self.download_tools.query_url
        self.doi_done = []

    def rxiv(
            self,
            interval,
            size,
            source=BIORXIV,
            update=None,
            makecsv=False,
            makehtml=False,
    ):
        
        if update:
            cursor_mark = update[CURSOR_MARK]
        else:
            cursor_mark = 0
        total_number_of_results = 0
        total_papers_list = []
        logging.info("Making Request to rxiv")
        while len(total_papers_list) <= size:
            total_number_of_results, total_papers_list, papers_list = self.make_request_add_papers(
                cursor_mark,
                interval,
                source,
                total_number_of_results,
                total_papers_list,
            )
            if len(papers_list) == 0:
                logging.warning("No more papers found")
                break
            cursor_mark += 1
        json_return_dict = {}
        for paper in total_papers_list:
            if update:
                if paper[DOI] not in update[TOTAL_JSON_OUTPUT]:
                    json_return_dict[paper[DOI]] = paper
            else:
                json_return_dict[paper[DOI]] = paper
            if len(json_return_dict) >= size:
                break

        for paper in json_return_dict:
            self.download_tools._add_download_status_keys(
                paper, json_return_dict)
        result_dict = self.download_tools.adds_new_results_to_metadata_dictionary(
            cursor_mark, json_return_dict, total_number_of_results, update=update)

        return_dict = result_dict[NEW_RESULTS][TOTAL_JSON_OUTPUT]
        self.download_tools.handle_creation_of_csv_html_xml(
            makecsv=makecsv,
            makehtml=makehtml,
            makexml=False,
            return_dict=return_dict,
            name=RXIV_RESULT,
        )
        return result_dict

    def make_request_add_papers(
            self, cursor_mark, interval, source, total_number_of_results, total_papers_list
    ):
        
        self.make_request_url_for_rxiv(cursor_mark, interval, source)
        request_handler = self.post_request()
        request_dict = json.loads(request_handler.text)
        papers_list = request_dict[COLLECTION]
        final_list = []
        for paper in papers_list:
            if paper[DOI] not in self.doi_done:
                final_list.append(paper)
                self.doi_done.append(paper[DOI])
        if TOTAL in request_dict[MESSAGES][0]:
            total_number_of_results = request_dict[MESSAGES][0][TOTAL]
        total_papers_list += final_list
        return total_number_of_results, total_papers_list, final_list

    def post_request(self):
        
        start = time.time()
        request_handler = requests.post(self.get_url)
        stop = time.time()
        logging.debug("*/Got the Query Result */")
        logging.debug("Time elapsed: %s", (stop - start))
        return request_handler

    def make_request_url_for_rxiv(self, cursor_mark, interval, source):
        
        if type(interval) == int:
            self.get_url = "https://api.biorxiv.org/details/{source}/{interval}".format(
                source=source, interval=interval
            )
        else:
            self.get_url = self.download_tools.query_url.format(
                source=source, interval=interval, cursor=cursor_mark
            )

    def rxiv_update(
            self,
            interval,
            size,
            source=BIORXIV,
            update=None,
            makecsv=False,
            makexml=False,
            makehtml=False,
    ):
        
        os.chdir(os.path.dirname(update))
        update = self.download_tools.readjsondata(update)
        logging.info("Reading old json metadata file")
        self.download_and_save_results(
            interval,
            size,
            update=update,
            source=source,
            makecsv=makecsv,
            makexml=makexml,
            makehtml=makehtml,
        )

    def download_and_save_results(
            self,
            interval,
            size,
            source,
            update=False,
            makecsv=False,
            makexml=False,
            makehtml=False,
    ):
        
        if update and type(interval) == int:
            raise PygetpapersError("Update will not work if date not provided")

        result_dict = self.rxiv(
            interval,
            size,
            update=update,
            source=source,
            makecsv=makecsv,
            makehtml=makehtml,
        )
        if makexml:
            logging.info("Making xml for paper")
            dict_of_papers = result_dict[NEW_RESULTS][TOTAL_JSON_OUTPUT]
            self.make_xml_for_rxiv(
                dict_of_papers, JATSXML, DOI, FULLTEXT_XML)
        self.download_tools.make_json_files_for_paper(
            result_dict[NEW_RESULTS], updated_dict=result_dict[UPDATED_DICT], paper_key=DOI,
            name_of_file=RXIV_RESULT
        )

    def make_xml_for_rxiv(
            self, dict_of_papers, xml_identifier, paper_id_identifier, filename
    ):
        
        for paper in tqdm(dict_of_papers):
            dict_of_paper = dict_of_papers[paper]
            xml_url = dict_of_paper[xml_identifier]
            doi_of_paper = dict_of_paper[paper_id_identifier]
            url_encoded_doi_of_paper = self.download_tools.url_encode_id(
                doi_of_paper)
            self.download_tools.check_or_make_directory(
                url_encoded_doi_of_paper)
            path_to_save_xml = os.path.join(
                str(os.getcwd()), url_encoded_doi_of_paper, filename
            )
            self.download_tools.queries_the_url_and_writes_response_to_destination(
                xml_url, path_to_save_xml)

    def noexecute(self, query_namespace):
        
        time_interval = query_namespace["date_or_number_of_papers"]
        source = query_namespace["api"]
        result_dict = self.rxiv(
            time_interval, size=10, source=source)
        totalhits = result_dict[NEW_RESULTS][TOTAL_HITS]
        logging.info("Total number of hits for the query are %s", totalhits)

    def update(self, query_namespace):
        
        update_file_path = self.download_tools.get_metadata_results_file()
        logging.info(
            "Please ensure that you are providing the same --api as the one in the corpus or you "
            "may get errors")
        self.rxiv_update(
            query_namespace["date_or_number_of_papers"],
            query_namespace["limit"],
            source=query_namespace["api"],
            update=update_file_path,
            makecsv=query_namespace["makecsv"],
            makexml=query_namespace["xml"],
            makehtml=query_namespace["makehtml"],
        )

    def apipaperdownload(self, query_namespace):
        
        self.download_and_save_results(
            query_namespace["query"],
            query_namespace["limit"],
            query_namespace["api"],
            makecsv=query_namespace["makecsv"],
            makexml=query_namespace["xml"],
            makehtml=query_namespace["makehtml"],
        )
