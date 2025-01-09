import json
import os
import re
import time

import pandas as pd
from tqdm import tqdm

from evaluation_suite.evaluate import (
    compare_multi_pandas_table,
    compare_pandas_table,
    get_snowflake_sql_result,
    get_sqlite_result,
    load_jsonl_to_dict,
)

"""
usage:

lite_evaluator_sqlite = create_evaluator()
score = lite_evaluator_sqlite(db, qid, pred_sql)
"""


def create_evaluator():

    eval_standard_dict = load_jsonl_to_dict("evaluation_suite/gold/spider2lite_eval.jsonl")
    os.makedirs(".temp/sqlite", exist_ok=True)
    os.makedirs(".temp/snowflake", exist_ok=True)

    def _eval(db, instance_id, pred_sql_query: str):
        s_time = time.time()
        if instance_id.startswith("local"):
            _save_dir = ".temp/sqlite"
            db_path = f"resource/databases/spider2-localdb/{db}.sqlite"
            assert os.path.exists(db_path), f"Database {db_path} does not exist!"
            exe_flag, dbms_error_info = get_sqlite_result(
                db_path=db_path, query=pred_sql_query, save_dir=_save_dir, file_name=f"{instance_id}.csv"
            )

        elif instance_id.startswith("sf"):
            _save_dir = ".temp/snowflake"
            exe_flag, dbms_error_info = get_snowflake_sql_result(
                sql_query=pred_sql_query,
                database_id=db,
                is_save=True,
                save_dir=_save_dir,
                file_name=f"{instance_id}.csv",
            )

        else:
            raise ValueError(f"Instance id {instance_id} does not start with 'local' or 'sf'!")

        e_time = time.time()

        error_info = None
        if exe_flag == False:
            score = 0
            error_info = dbms_error_info
        else:
            pred_pd = pd.read_csv(os.path.join(_save_dir, f"{instance_id}.csv"))

            # load golden sql from csv(s)
            pattern = re.compile(rf"^{re.escape(instance_id)}(_[a-z])?\.csv$")
            all_files = os.listdir("evaluation_suite/gold/exec_result")
            csv_files = [file for file in all_files if pattern.match(file)]
            if len(csv_files) == 1:
                gold_pd = pd.read_csv(os.path.join("evaluation_suite/gold/exec_result", f"{instance_id}.csv"))
                try:
                    score = compare_pandas_table(
                        pred_pd,
                        gold_pd,
                        eval_standard_dict.get(instance_id)["condition_cols"],
                        eval_standard_dict.get(instance_id)["ignore_order"],
                    )
                except Exception as e:
                    # print(f"An error occurred: {e}")
                    score = 0
                    error_info = "Python Script Error:" + str(e)
                if score == 0 and error_info is None:
                    error_info = "Result Error"
            elif len(csv_files) > 1:
                gold_pds = [
                    pd.read_csv(os.path.join("evaluation_suite/gold/exec_result", file)) for file in csv_files
                ]
                score = compare_multi_pandas_table(
                    pred_pd,
                    gold_pds,
                    eval_standard_dict.get(instance_id)["condition_cols"],
                    eval_standard_dict.get(instance_id)["ignore_order"],
                )
                if score == 0 and error_info is None:
                    error_info = "Result Error"

        res = {
            "instance_id": instance_id,
            "db": db,
            "pred_sql": pred_sql_query,
            "score": score,
            "error_info": error_info,
            "exec_time": e_time - s_time,
        }
        return res

    return _eval


def test_lite_eval():
    import random

    from loguru import logger

    lite_evaluator_sqlite = create_evaluator()

    _dir = "official_res/1105-zeroshot_spider2-lite_CTX-200/RESULTS_MODEL-gpt-4o-2024-08-06-SQL-postprocessed"

    data = []
    with open("spider2-lite.jsonl", "r") as f:
        for line in f:
            d = json.loads(line)
            instance_id = d["instance_id"]
            if not instance_id.startswith("local") and not instance_id.startswith("sf"):
                continue
            if os.path.exists(os.path.join(_dir, f"{instance_id}.sql")):
                with open(os.path.join(_dir, f"{instance_id}.sql"), "r") as f:
                    d["pred_sql"] = f.read()
                data.append(d)
            # else:
            #     logger.warning(f"File {os.path.join(_dir, f'{instance_id}.sql')} does not exist")

    logger.info(f"Loaded {len(data)} items")

    random.seed(42)
    random.shuffle(data)
    data = data[:100]
    logger.info(f"Randomly selected {len(data)} items")

    scores_sqlite, scores_snowflake = [], []
    for item in tqdm(data, desc="Evaluating", ncols=100):
        instance_id = item["instance_id"]
        db = item["db"]
        pred_sql = item["pred_sql"]
        res = lite_evaluator_sqlite(db, instance_id, pred_sql)
        if instance_id.startswith("local"):
            scores_sqlite.append(res["score"])
        elif instance_id.startswith("sf"):
            scores_snowflake.append(res["score"])

    print(
        f"Average score: \n"
        f"local: {sum(scores_sqlite) / len(scores_sqlite)}, snowflake: {sum(scores_snowflake) / len(scores_snowflake)}"
        f"overall: {(sum(scores_sqlite) + sum(scores_snowflake)) / (len(scores_sqlite) + len(scores_snowflake))}"
    )


if __name__ == "__main__":
    # python evaluation_suite/lite_eval.py
    test_lite_eval()
