# import debugpy; debugpy.connect(('127.0.0.1', 5688))
import json
import re
import pandas as pd
import math
import os
import pandas as pd
import argparse
from google.cloud import bigquery
import shutil
import sqlite3
from tqdm import tqdm
import snowflake.connector
import sys
from google.oauth2 import service_account
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
import time


def timeout(seconds):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            if end_time - start_time > seconds:
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
            return result
        return wrapper
    return decorator


class TeeOutput:
    def __init__(self, filename):
        self.console = sys.stdout
        self.file = open(filename, 'w')
    
    def write(self, message):
        self.console.write(message)
        self.file.write(message)
    
    def flush(self):
        self.console.flush()
        self.file.flush()
    
    def close(self):
        self.file.close()

sys.stdout = TeeOutput('log.txt')
sys.stderr = sys.stdout

TOTAL_GB_PROCESSED = 0.0


byte_output_dict = {}

def load_jsonl_to_dict(jsonl_file):
    data_dict = {}
    with open(jsonl_file, 'r') as file:
        for line in file:
            item = json.loads(line.strip())
            instance_id = item['instance_id']
            data_dict[instance_id] = item
    return data_dict

def load_json_list_to_dict(json_file_path):
    with open(json_file_path, 'r', encoding='utf-8') as file:
        data_list = json.load(file)
    data_dict = {item['instance_id']: item for item in data_list}
    return data_dict


def compare_multi_pandas_table(pred, multi_gold, multi_condition_cols=[], multi_ignore_order=False):
    # print('multi_condition_cols', multi_condition_cols)

    if multi_condition_cols == [] or multi_condition_cols == [[]] or multi_condition_cols == [None] or multi_condition_cols == None:
        multi_condition_cols = [[] for _ in range(len(multi_gold))]
    elif len(multi_gold) > 1 and not all(isinstance(sublist, list) for sublist in multi_condition_cols):
        multi_condition_cols = [multi_condition_cols for _ in range(len(multi_gold))]
    multi_ignore_order = [multi_ignore_order for _ in range(len(multi_gold))]

    for i, gold in enumerate(multi_gold):
        if compare_pandas_table(pred, gold, multi_condition_cols[i], multi_ignore_order[i]):
            return 1
    return 0


def compare_pandas_table(pred, gold, condition_cols=[], ignore_order=False):
    """_summary_

    Args:
        pred (Dataframe): _description_
        gold (Dataframe): _description_
        condition_cols (list, optional): _description_. Defaults to [].
        ignore_order (bool, optional): _description_. Defaults to False.

    """
    # print('condition_cols', condition_cols)
    
    tolerance = 1e-2

    def vectors_match(v1, v2, tol=tolerance, ignore_order_=False):
        if ignore_order_:
            v1, v2 = (sorted(v1, key=lambda x: (x is None, str(x), isinstance(x, (int, float)))),
                    sorted(v2, key=lambda x: (x is None, str(x), isinstance(x, (int, float)))))
        if len(v1) != len(v2):
            return False
        for a, b in zip(v1, v2):
            if pd.isna(a) and pd.isna(b):
                continue
            elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if not math.isclose(float(a), float(b), abs_tol=tol):
                    return False
            elif a != b:
                return False
        return True
    
    if condition_cols != []:
        gold_cols = gold.iloc[:, condition_cols]
    else:
        gold_cols = gold
    pred_cols = pred

    t_gold_list = gold_cols.transpose().values.tolist()
    t_pred_list = pred_cols.transpose().values.tolist()
    score = 1
    for _, gold in enumerate(t_gold_list):
        if not any(vectors_match(gold, pred, ignore_order_=ignore_order) for pred in t_pred_list):
            score = 0
        else:
            for j, pred in enumerate(t_pred_list):
                if vectors_match(gold, pred, ignore_order_=ignore_order):
                    break

    return score


def get_bigquery_sql_result(sql_query, is_save, save_dir=None, file_name="result.csv"):
    """
    is_save = True, output a 'result.csv'
    if_save = False, output a string
    """
    # os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "bigquery_credential.json"
    client = bigquery.Client(credentials=service_account.Credentials.from_service_account_file('evaluation_suite/.bigquery_credential.json'))

    try:
        query_job = client.query(sql_query)
        results = query_job.result().to_dataframe() 
        total_bytes_processed = query_job.total_bytes_processed
        gb_processed = total_bytes_processed / (1024 ** 3)
        print(f"GB processed: {gb_processed:.5f} GB")
        global TOTAL_GB_PROCESSED
        TOTAL_GB_PROCESSED += gb_processed
        # print(f"Total GB processed: {TOTAL_GB_PROCESSED:.5f} GB")
        
        if results.empty:
            print("No data found for the specified query.")
            results.to_csv(os.path.join(save_dir, file_name), index=False)
            return None, None
        else:
            if is_save:
                results.to_csv(os.path.join(save_dir, file_name), index=False)
                return None, None
            else:
                value = results.iat[0, 0]
                return value, None
    except Exception as e:
        print("Error occurred while fetching data: ", e)  
        return False, str(e)
    return True, None


def get_snowflake_sql_result(sql_query, database_id, is_save, save_dir=None, file_name="result.csv"):
    """
    is_save = True, output a 'result.csv'
    if_save = False, output a string
    """
    snowflake_credential = json.load(open('evaluation_suite/.snowflake_credential.json'))
    conn = snowflake.connector.connect(
        database=database_id,
        network_timeout=180,
        **snowflake_credential
    )
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql_query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(results, columns=columns)
        if df.empty:
            print("No data found for the specified query.")
            return False, "No data found for the specified query."
        else:
            if is_save:
                df.to_csv(os.path.join(save_dir, file_name), index=False)
                return None, None
    except Exception as e:
        print("Error occurred while fetching data: ", e)  
        return False, str(e)

@timeout(60*3)
def get_sqlite_result(db_path, query, save_dir=None, file_name="result.csv", chunksize=500):
    conn = sqlite3.connect(db_path)
    # memory_conn = sqlite3.connect(':memory:')
    # conn.backup(memory_conn)
    s_time = time.time()
    try:
        if save_dir:
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            for i, chunk in enumerate(pd.read_sql_query(query, conn, chunksize=chunksize)):
                mode = 'a' if i > 0 else 'w'
                header = i == 0
                chunk.to_csv(os.path.join(save_dir, file_name), mode=mode, header=header, index=False)
        else:
            df = pd.read_sql_query(query, conn)
            e_time = time.time()
            if e_time - s_time > 10:
                print(f"Query {query} took {e_time - s_time} seconds")
            return True, df

    except Exception as e:
        # print(f"An error occurred: {e}")
        return False, str(e)

    finally:
        # memory_conn.close()
        conn.close()
    
    e_time = time.time()
    if e_time - s_time > 10:
        print(f"Query {query} took {e_time - s_time} seconds")
    return True, None


# @timeout(60*3)
def evaluate_single_id(id, args, eval_standard_dict, spider2sql_metadata, gold_sql_dir, gold_result_dir):
    error_info = None
    print(f"Evaluating {id}")

    if args.mode == "sql":
        pred_sql_query = open(os.path.join(args.result_dir, f"{id}.sql")).read()
        if id.startswith("bq") or id.startswith("ga"):
            
            # NOTE: skip bigquery data
            return None
            
            exe_flag, dbms_error_info = get_bigquery_sql_result(pred_sql_query, True, ".temp", f"{id}.csv")  
            if exe_flag == False: 
                score = 0
                error_info = dbms_error_info
            else:                    
                pred_pd = pd.read_csv(os.path.join(".temp", f"{id}.csv"))  
                if '_' in id:
                    pattern = re.compile(rf'^{re.escape(id)}(_[a-z])?\.csv$')
                else:
                    pattern = re.compile(rf'^{re.escape(id)}(_[a-z])?\.csv$')
                    
                all_files = os.listdir(gold_result_dir)
                csv_files = [file for file in all_files if pattern.match(file)]
                if len(csv_files) == 1:
                    gold_pd = pd.read_csv(os.path.join(gold_result_dir, f"{id}.csv"))
                    try:
                        score = compare_pandas_table(pred_pd, gold_pd, eval_standard_dict.get(id)['condition_cols'], eval_standard_dict.get(id)['ignore_order'])
                    except Exception as e:
                        # print(f"An error occurred: {e}")
                        score = 0
                        error_info = 'Python Script Error:' + str(e)
                    if score == 0 and error_info is None:
                        error_info = 'Result Error'     
                elif len(csv_files) > 1:
                    csv_files = sorted(csv_files)
                    gold_pds = [pd.read_csv(os.path.join(gold_result_dir, file)) for file in csv_files]
                    score = compare_multi_pandas_table(pred_pd, gold_pds, eval_standard_dict.get(id)['condition_cols'], eval_standard_dict.get(id)['ignore_order'])
                    if score == 0 and error_info is None:
                        error_info = 'Result Error'

        elif id.startswith("local"):
            exe_flag, dbms_error_info = get_sqlite_result(f"resource/databases/spider2-localdb/{spider2sql_metadata.get(id)['db']}.sqlite", pred_sql_query, ".temp", f"{id}.csv" )
            if exe_flag == False:
                score = 0
                error_info = dbms_error_info
            else:
                pred_pd = pd.read_csv(os.path.join(".temp", f"{id}.csv"))  
                pattern = re.compile(rf'^{re.escape(id)}(_[a-z])?\.csv$')

                all_files = os.listdir(gold_result_dir)
                csv_files = [file for file in all_files if pattern.match(file)]
                if len(csv_files) == 1:
                    gold_pd = pd.read_csv(os.path.join(gold_result_dir, f"{id}.csv"))
                    try:
                        score = compare_pandas_table(pred_pd, gold_pd, eval_standard_dict.get(id)['condition_cols'], eval_standard_dict.get(id)['ignore_order'])
                    except Exception as e:
                        # print(f"An error occurred: {e}")
                        score = 0
                        error_info = 'Python Script Error:' + str(e)
                    if score == 0 and error_info is None:
                        error_info = 'Result Error'     
                elif len(csv_files) > 1:
                    gold_pds = [pd.read_csv(os.path.join(gold_result_dir, file)) for file in csv_files]
                    score = compare_multi_pandas_table(pred_pd, gold_pds, eval_standard_dict.get(id)['condition_cols'], eval_standard_dict.get(id)['ignore_order'])
                    if score == 0 and error_info is None:
                        error_info = 'Result Error'
        
        elif id.startswith("sf"):
            database_id = spider2sql_metadata[id]['db']
            exe_flag, dbms_error_info = get_snowflake_sql_result(pred_sql_query, database_id, True, ".temp", f"{id}.csv") 
            if exe_flag == False: 
                score = 0
                error_info = dbms_error_info
            else:                    
                pred_pd = pd.read_csv(os.path.join(".temp", f"{id}.csv"))  
                pattern = re.compile(rf'^{re.escape(id)}(_[a-z])?\.csv$')
                    
                all_files = os.listdir(gold_result_dir)
                csv_files = [file for file in all_files if pattern.match(file)]
                if len(csv_files) == 1:
                    gold_pd = pd.read_csv(os.path.join(gold_result_dir, f"{id}.csv"))
                    try:
                        score = compare_pandas_table(pred_pd, gold_pd, eval_standard_dict.get(id)['condition_cols'], eval_standard_dict.get(id)['ignore_order'])
                    except Exception as e:
                        # print(f"An error occurred: {e}")
                        score = 0
                        error_info = 'Python Script Error:' + str(e)
                    if score == 0 and error_info is None:
                        error_info = 'Result Error'     
                elif len(csv_files) > 1:
                    gold_pds = [pd.read_csv(os.path.join(gold_result_dir, file)) for file in csv_files]
                    score = compare_multi_pandas_table(pred_pd, gold_pds, eval_standard_dict.get(id)['condition_cols'], eval_standard_dict.get(id)['ignore_order'])
                    if score == 0 and error_info is None:
                        error_info = 'Result Error'                        
    
    elif args.mode == "exec_result":
        try:
            pred_pd = pd.read_csv(os.path.join(args.result_dir, f"{id}.csv"))
            if '_' in id:
                pattern = re.compile(rf'^{re.escape(id)}(_[a-z])?\.csv$')
            else:
                pattern = re.compile(rf'^{re.escape(id)}(_[a-z])?\.csv$')
            all_files = os.listdir(gold_result_dir)
            csv_files = [file for file in all_files if pattern.match(file)]

            if len(csv_files) == 1:
                gold_pd = pd.read_csv(os.path.join(gold_result_dir, f"{id}.csv"))
                score = compare_pandas_table(pred_pd, gold_pd, eval_standard_dict.get(id)['condition_cols'], eval_standard_dict.get(id)['ignore_order'])
            elif len(csv_files) > 1:
                gold_pds = [pd.read_csv(os.path.join(gold_result_dir, file)) for file in csv_files]
                score = compare_multi_pandas_table(pred_pd, gold_pds, eval_standard_dict.get(id)['condition_cols'], eval_standard_dict.get(id)['ignore_order'])
        except:
            print("{id} ERROR!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

    return {
        "instance_id": id, 
        "score": score,
        "pred_sql": pred_sql_query if args.mode == "sql" else None,
        "error_info": error_info
    }

def evaluate_spider2sql(args):
    gold_sql_dir = os.path.join(args.gold_dir, "sql")
    gold_result_dir = os.path.join(args.gold_dir, "exec_result")
    
    eval_standard_dict = load_jsonl_to_dict(os.path.join(args.gold_dir, "spider2lite_eval.jsonl"))
    spider2sql_metadata = load_jsonl_to_dict("spider2-lite.jsonl")
        
    gold_ids = []
    pred_ids = []
    if args.mode == "sql":
        for file in os.listdir(args.result_dir):
            if file.endswith(".sql"):
                pred_ids.append(file.split(".")[0])
    elif args.mode == 'exec_result':
        for file in os.listdir(args.result_dir):
            if file.endswith(".csv"):
                pred_ids.append(file.split(".")[0])

    # skip the bigquery data.
    # pred_ids = [id for id in pred_ids if not id.startswith("bq") and not id.startswith("ga")]
    # pred_ids = [id for id in pred_ids if not id.startswith("sf")]

    gold_ids = list(eval_standard_dict.keys())
    eval_ids = list(set(gold_ids).intersection(pred_ids))

    assert len(eval_ids) > 0, f"No evaluation ids found, check your result_dir: {args.result_dir} and gold_dir: {args.gold_dir}"

    eval_ids = sorted(eval_ids)  # sorted, for reproduce result
    output_results = []

    # eval_ids = eval_ids[:230]
    # eval_ids = ["sf044"]

    # debug
    # for id in eval_ids[:]:
    #     evaluate_single_id(id, args, eval_standard_dict, spider2sql_metadata, gold_sql_dir, gold_result_dir)
    # exit()

    # multi-thread
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(evaluate_single_id, id, args, eval_standard_dict, spider2sql_metadata, gold_sql_dir, gold_result_dir) for id in eval_ids]
        try:
            for future in tqdm(as_completed(futures, timeout=60*3), total=len(eval_ids), desc="Evaluating"):
                try:
                    r = future.result()
                    if r is not None:
                        output_results.append(r)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    executor.shutdown(wait=False)
                    sys.exit(1)
        except KeyboardInterrupt:
            print("User interrupt execution")
            executor.shutdown(wait=False) 
            sys.exit(1)

    # print({item['instance_id']: item['score'] for item in output_results})  
    correct_examples = sum([item['score'] for item in output_results]) 

    print()
    print(f"Final score: {correct_examples / len(output_results)}, Correct examples: {correct_examples}, Total examples: {len(output_results)}")
    print(f"Real score: {correct_examples / 547}, Correct examples: {correct_examples}, Total examples: 547")


    DEBUG_PREFIX = "SQL_DEBUG_" if args.is_sql_debug else ""
    with open(
        os.path.join(args.result_dir, f"{DEBUG_PREFIX}eval_result_with_error_infos.json"), 'w'
    ) as f:
        json.dump(output_results, f, indent=4)

    # print("TOTAL_GB_PROCESSED: ",TOTAL_GB_PROCESSED)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run evaluations for NLP models.")
    parser.add_argument("--mode", type=str, choices=["sql", "exec_result"], default='sql', help="Mode of submission results")
    parser.add_argument("--result_dir", type=str, default="spider2sql_example_submit_result", help="Result directory")
    parser.add_argument("--gold_dir", type=str, default="evaluation_suite/gold", help="Result directory")
    parser.add_argument("--is_sql_debug", action="store_true", default=False)
    args = parser.parse_args()
    
    if os.path.exists(".temp"):
        shutil.rmtree(".temp")
    os.makedirs(".temp")

    evaluate_spider2sql(args)