
```bash
python spider_agent_setup_snow.py

# 需要docker，不弄了
python run.py --model gpt-4o -s test1

# 
python evaluation_suite/evaluate.py --result_dir evaluation_suite/example_submission_folder
```




- id: sf_bq033
- db: PATENTS
- question: How many U.S. publications related to IoT (where the abstract includes the phrase 'internet of things') were filed each month from 2008 to 2022, including months with no filings?
- q_cn: 2008年至2022年期间，每个月有多少份与物联网（摘要中包含“物联网”这一短语）相关的美国出版物被提交，包括那些没有提交的月份？
- SQL: 
```sql
WITH Patent_Matches AS (
    SELECT
      TO_DATE(CAST(ANY_VALUE(patentsdb."filing_date") AS STRING), 'YYYYMMDD') AS Patent_Filing_Date,
      patentsdb."application_number" AS Patent_Application_Number,
    --   MAX(abstract_info.value:"text") AS Patent_Title, 似乎没有用
    --   MAX(abstract_info.value:"language") AS Patent_Title_Language 似乎没有用
    FROM
      PATENTS.PATENTS.PUBLICATIONS AS patentsdb,
      LATERAL FLATTEN(input => patentsdb."abstract_localized") AS abstract_info
    WHERE
      LOWER(abstract_info.value:"text") LIKE '%internet of things%'
      AND patentsdb."country_code" = 'US'
    GROUP BY
      Patent_Application_Number
),

Date_Series_Table AS (
    SELECT
        DATEADD(day, seq4(), DATE '2008-01-01') AS day,
        0 AS Number_of_Patents
    FROM
        TABLE(
            GENERATOR(
                ROWCOUNT => 5479
            )
        )
    ORDER BY
        day
)

SELECT
  TO_CHAR(Date_Series_Table.day, 'YYYY-MM') AS Patent_Date_YearMonth,
  COUNT(Patent_Matches.Patent_Application_Number) AS Number_of_Patent_Applications
FROM
  Date_Series_Table
  LEFT JOIN Patent_Matches
    ON Date_Series_Table.day = Patent_Matches.Patent_Filing_Date
WHERE
    Date_Series_Table.day < DATE '2023-01-01'
GROUP BY
  TO_CHAR(Date_Series_Table.day, 'YYYY-MM')
ORDER BY
  Patent_Date_YearMonth;
```

- id: sf_local004
- db: E_COMMERCE
- question: Could you tell me the number of orders, average payment per order and customer lifespan in weeks of the 3 custumers with the highest average payment per order. Attention: I want the lifespan in float number if it's longer than one week, otherwise set it to be 1.0.
- q_cn: 你能告诉我平均每单支付金额最高的前3位客户的订单数量、平均每单支付金额以及客户生命周期（以周为单位）吗？注意：如果生命周期超过一周，请以小数形式表示；如果不超过一周，则设置为1.0。
- SQL: 
```sql
WITH CustomerData AS (
    SELECT
        "customer_unique_id",
        COUNT(DISTINCT E_COMMERCE.E_COMMERCE.ORDERS."order_id") AS order_count,
        SUM(TO_NUMBER("payment_value")) AS total_payment,
        DATE_PART('day', MIN(TO_TIMESTAMP("order_purchase_timestamp", 'YYYY-MM-DD HH24:MI:SS'))) AS first_order_day,
        DATE_PART('day', MAX(TO_TIMESTAMP("order_purchase_timestamp", 'YYYY-MM-DD HH24:MI:SS'))) AS last_order_day
    FROM E_COMMERCE.E_COMMERCE.CUSTOMERS 
        JOIN E_COMMERCE.E_COMMERCE.ORDERS USING ("customer_id")
        JOIN E_COMMERCE.E_COMMERCE.ORDER_PAYMENTS USING ("order_id")
    GROUP BY "customer_unique_id"
)
SELECT
    "customer_unique_id",
    order_count AS PF,
    ROUND(total_payment / order_count, 2) AS AOV,
    CASE
        WHEN (last_order_day - first_order_day) < 7 THEN
            1
        ELSE
            (last_order_day - first_order_day) / 7
        END AS ACL
FROM CustomerData
ORDER BY AOV DESC
LIMIT 3;
```

- id: sf_local009
- db: AIRLINES
- question: What is the distance of the longest route where Abakan is either the departure or destination city (in kilometers)?
- q_cn: 阿巴坎作为出发城市或目的地城市的最长路线距离是多少公里？
- SQL: 
```sql
WITH FLIGHT_INFO AS (
    SELECT    
        FLIGHTS."flight_id",
        PARSE_JSON(DEPARTURE."city"):"en" AS "from_city",
        CAST(SUBSTR(DEPARTURE."coordinates", 2, POSITION(',' IN DEPARTURE."coordinates") - 2) AS DOUBLE) AS "from_longitude",
        CAST(SUBSTR(DEPARTURE."coordinates", POSITION(',' IN DEPARTURE."coordinates") + 1, LENGTH(DEPARTURE."coordinates") - POSITION(',' IN DEPARTURE."coordinates") - 2) AS DOUBLE) AS "from_latitude",
        PARSE_JSON(ARRIVAL."city"):"en" AS "to_city",
        CAST(SUBSTR(ARRIVAL."coordinates", 2, POSITION(',' IN ARRIVAL."coordinates") - 2) AS DOUBLE) AS "to_longitude",
        CAST(SUBSTR(ARRIVAL."coordinates", POSITION(',' IN ARRIVAL."coordinates") + 1, LENGTH(ARRIVAL."coordinates") - POSITION(',' IN ARRIVAL."coordinates") - 2) AS DOUBLE) AS "to_latitude"
    FROM
        AIRLINES.AIRLINES.FLIGHTS 
    LEFT JOIN AIRLINES.AIRLINES.AIRPORTS_DATA AS DEPARTURE ON FLIGHTS."departure_airport" = DEPARTURE."airport_code"
    LEFT JOIN AIRLINES.AIRLINES.AIRPORTS_DATA AS ARRIVAL ON FLIGHTS."arrival_airport" = ARRIVAL."airport_code"
),
DISTANCES AS (
    SELECT
        "flight_id",
        "from_city",
        "to_city",
        CASE
            WHEN "from_city" < "to_city" THEN "from_city" ELSE "to_city" END AS "city1",
        CASE
            WHEN "from_city" < "to_city" THEN "to_city" ELSE "from_city" END AS "city2",
        2 * 6371 * ASIN(SQRT(
            POWER(SIN(RADIANS(("to_latitude" - "from_latitude") / 2)), 2) +
            COS(RADIANS("from_latitude")) * COS(RADIANS("to_latitude")) *
            POWER(SIN(RADIANS(("to_longitude" - "from_longitude") / 2)), 2)
        )) AS "distance_km"
    FROM FLIGHT_INFO
),
ALL_Route AS (
    SELECT
        "city1",
        "city2",
        "distance_km",
        COUNT(*) AS "number_of_flights" -- Count flights for both directions
    FROM DISTANCES
    WHERE ("city1" = 'Abakan' OR "city2" = 'Abakan')
    GROUP BY "city1", "city2", "distance_km"
)
SELECT 
    "distance_km"
FROM ALL_Route
ORDER BY "distance_km" DESC
LIMIT 1;
```