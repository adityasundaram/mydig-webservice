from optparse import OptionParser
import json
import codecs
from elasticsearch import Elasticsearch

es = Elasticsearch(['http://10.1.94.103:9201'])


def create_query(field_name=None, method=None, tlds=None, search_in_tlds=True):
    if tlds and not field_name and not method:
        if search_in_tlds:
            return {
                "query": {
                    "terms": {
                       "knowledge_graph.website.key": tlds
                    }
                },
                "size": 0
            }
        else:
            return {
                "query": {
                    "filtered": {
                        "query": {"match_all": {}},
                        "filter": {
                            "not": {
                                "filter": {
                                    "terms": {
                                        "knowledge_graph.website.key": tlds
                                    }
                                }
                            }
                        }
                    }
                },
                "size": 0
            }
    if not field_name or not method or not tlds:
        return  "{\"query\": {\"match_all\": {}}, \"size\": 0}"
    field_path = 'knowledge_graph.{}.provenance.method'.format(field_name)
    term_q = dict()
    term_q['term'] = dict()
    term_q['term'][field_path] = method
    if search_in_tlds:
        query = {
                   "query": {
                      "filtered": {
                         "query": {
                            "match_all": {}
                         },
                         "filter": {
                            "and": {
                               "filters": [

                               ]
                            }
                         }
                      }
                   },
                    "size": 0
                }
        terms_q = dict()
        terms_q['terms'] = dict()
        terms_q['terms']['knowledge_graph.website.key'] = tlds
        query['query']['filtered']['filter']['and']['filters'].append(terms_q)
    else:
        query ={
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "and": {
                            "filters": [

                            ]
                        }
                    }
                }
            },
            "size": 0
        }
        not_terms_q = {
                        "not": {
                            "filter": {
                                "terms": {
                                    "knowledge_graph.website.key": tlds
                                }
                            }
                        }
                    }
        query['query']['filtered']['filter']['and']['filters'].append(not_terms_q)
    query['query']['filtered']['filter']['and']['filters'].append(term_q)
    return query


def generate_report(master_config, domain_name, inferlink_rules):
    index = master_config['index']['full']
    report = dict()
    report['short_tail'] = dict()
    report['long_tail'] = dict()
    inferlink_tlds = inferlink_rules.keys()
    report['domain_name'] = domain_name
    report['short_tail']['inferlink_extractions'] = dict()
    report['short_tail']['custom_spacy_extractions'] = dict()
    report['short_tail']['glossary_extractions'] = dict()
    report['long_tail']['custom_spacy_extractions'] = dict()
    report['long_tail']['glossary_extractions'] = dict()
    report['short_tail']['georesolved_city_extractions'] = dict()
    report['long_tail']['georesolved_city_extractions'] = dict()
    report['long_tail']['total_docs'] = query_es(index, create_query(tlds=inferlink_tlds, search_in_tlds=False))['hits']['total']
    report['short_tail']['total_docs'] = query_es(index, create_query(tlds=inferlink_tlds))['hits']['total']
    if 'fields' in master_config:
        fields = master_config['fields']
        report['rule_names_by_tld'] = count_fields_inferlink_rules(inferlink_rules, fields.keys())
        report['total_fields'] = len(fields.keys())
        report['total_fields_with_glossaries'] = 0
        report['total_fields_with_custom_spacy'] = 0
        for k, v in fields.iteritems():
            if k == 'city':
                query = {
                   "query": {
                      "filtered": {
                         "query": {
                            "match_all": {}
                         },
                         "filter": {
                            "and": {
                               "filters": [
                                  {
                                     "exists": {
                                        "field": "knowledge_graph.city"
                                     }
                                  },
                                  {
                                     "terms": {
                                        "knowledge_graph.website.key": inferlink_tlds
                                     }
                                  }
                               ]
                            }
                         }
                      }
                   },
                    "size": 0
                }
                city_c_s  = query_es(index,  query=query)['hits']['total']
                if city_c_s > 0:
                    report['short_tail']['georesolved_city_extractions'][k] = city_c_s

                query = {
                   "query": {
                      "filtered": {
                         "query": {
                            "match_all": {}
                         },
                         "filter": {
                            "and": {
                               "filters": [
                                  {
                                     "exists": {
                                        "field": "knowledge_graph.city"
                                     }
                                  },
                                  {
                                     "not": {
                                        "filter": {
                                           "terms": {
                                              "knowledge_graph.website.key": inferlink_tlds
                                           }
                                        }
                                     }
                                  }
                               ]
                            }
                         }
                      }
                   }
                }
                city_c_l = query_es(index, query=query)['hits']['total']
                if city_c_l > 0:
                    report['long_tail']['georesolved_city_extractions'][k] = city_c_l
            if 'glossaries' in v and len(v['glossaries']) > 0:
                report['total_fields_with_glossaries'] += 1
                gs_s = query_es(index, query=create_query(field_name=k, method='extract_using_dictionary', tlds=inferlink_tlds))['hits']['total']
                if gs_s > 0:
                    report['short_tail']['glossary_extractions'][k] = gs_s

                gs_l = query_es(index, query=create_query(field_name=k, method='extract_using_dictionary',
                                                          tlds=inferlink_tlds, search_in_tlds=False))['hits']['total']
                if gs_l > 0:
                    report['long_tail']['glossary_extractions'][k] = gs_l
            if 'rule_extractor_enabled' in v and v['rule_extractor_enabled']:
                report['total_fields_with_custom_spacy'] += 1
                cps_s = query_es(index, query=create_query(field_name=k, method='extract_using_custom_spacy',
                                                         tlds=inferlink_tlds))['hits']['total']
                if cps_s > 0:
                    report['short_tail']['custom_spacy_extractions'][k] = cps_s

                cps_l = query_es(index, query=create_query(field_name=k, method='extract_using_custom_spacy',
                                                         tlds=inferlink_tlds, search_in_tlds=False))['hits']['total']
                if cps_l > 0:
                    report['long_tail']['custom_spacy_extractions'][k] = cps_l
            ies = query_es(index, query=create_query(field_name=k, method='inferlink', tlds=inferlink_tlds))['hits']['total']
            if ies > 0:
                report['short_tail']['inferlink_extractions'][k] = ies
    return report


def query_es(index, query):
    return es.search(index=index, body=query)


def count_fields_inferlink_rules(consolidated_rules, defined_fields):
    out = dict()
    for tld in consolidated_rules.keys():
        rules_list = consolidated_rules[tld]
        uniq_rule_names = set()
        for i in range(0, len(rules_list)):
            rules = rules_list[i]['rules']
            for j in range(0, len(rules)):
                rule = rules[j]
                r_name = rule['name']
                if 'title' not in r_name and 'description' not in r_name:
                    stripped_name = r_name.split('-')[0]
                    if stripped_name in defined_fields:
                        uniq_rule_names.add(stripped_name)
        out[tld] = dict()
        out[tld]['rules'] = list(uniq_rule_names)
        out[tld]['count'] = len(list(uniq_rule_names))
    return out

if __name__ == '__main__':
    parser = OptionParser()
    (c_options, args) = parser.parse_args()
    projects = ["atf_firearms_domain", "ce_domain", "narcotics_domain", "sec_domain", "domain5"]
    my_dig_projects_path = args[0]
    my_dig_inferlink_path = args[1]
    output_file = args[2]
    reports = list()
    for project in projects:
        master_config = json.load(codecs.open('{}/{}/{}'.format(my_dig_projects_path, project, 'master_config.json')))
        inferlink_rules = json.load(codecs.open('{}/{}/landmark/consolidated_rules.json'.format(my_dig_inferlink_path, project)))
        reports.append(generate_report(master_config, project, inferlink_rules))
    codecs.open(output_file, 'w').write(json.dumps(reports))