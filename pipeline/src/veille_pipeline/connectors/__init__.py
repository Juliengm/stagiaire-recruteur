from veille_pipeline.connectors.csv_dataset import CsvDatasetConnector
from veille_pipeline.connectors.gmail_alert import GmailAlertConnector
from veille_pipeline.connectors.html_list import HtmlListConnector
from veille_pipeline.connectors.pdf_page import PdfPageConnector
from veille_pipeline.connectors.reliefweb import ReliefWebConnector
from veille_pipeline.connectors.rss import RssConnector
from veille_pipeline.connectors.workable import WorkableConnector
from veille_pipeline.connectors.worldbank import WorldBankProcNoticesConnector

CONNECTORS = {c.kind: c for c in (RssConnector(), CsvDatasetConnector(), ReliefWebConnector(),
                                         WorldBankProcNoticesConnector(), GmailAlertConnector(),
                                         HtmlListConnector(), PdfPageConnector(),
                                         WorkableConnector())}
