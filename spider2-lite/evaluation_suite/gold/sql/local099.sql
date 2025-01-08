WITH YASH_CHOPRAS_PID AS (
    SELECT
        TRIM(P.PID) AS PID
    FROM
        Person P
    WHERE
        TRIM(P.Name) = 'Yash Chopra'
),
NUM_OF_MOV_BY_ACTOR_DIRECTOR AS (
    SELECT
        TRIM(MC.PID) AS ACTOR_PID,
        TRIM(MD.PID) AS DIRECTOR_PID,
        COUNT(DISTINCT TRIM(MD.MID)) AS NUM_OF_MOV
    FROM
        M_Cast MC
    JOIN
        M_Director MD ON TRIM(MC.MID) = TRIM(MD.MID)
    GROUP BY
        ACTOR_PID,
        DIRECTOR_PID
),
NUM_OF_MOVIES_BY_YC AS (
    SELECT
        NM.ACTOR_PID,
        NM.DIRECTOR_PID,
        NM.NUM_OF_MOV AS NUM_OF_MOV_BY_YC
    FROM
        NUM_OF_MOV_BY_ACTOR_DIRECTOR NM
    JOIN
        YASH_CHOPRAS_PID YCP ON NM.DIRECTOR_PID = YCP.PID
),
MAX_MOV_BY_OTHER_DIRECTORS AS (
    SELECT
        ACTOR_PID,
        MAX(NUM_OF_MOV) AS MAX_NUM_OF_MOV
    FROM
        NUM_OF_MOV_BY_ACTOR_DIRECTOR NM
    JOIN
        YASH_CHOPRAS_PID YCP ON NM.DIRECTOR_PID <> YCP.PID
    GROUP BY
        ACTOR_PID
),
ACTORS_MOV_COMPARISION AS (
    SELECT
        NMY.ACTOR_PID,
        CASE WHEN NMY.NUM_OF_MOV_BY_YC > IFNULL(NMO.MAX_NUM_OF_MOV, 0) THEN 'Y' ELSE 'N' END AS MORE_MOV_BY_YC
    FROM
        NUM_OF_MOVIES_BY_YC NMY
    LEFT OUTER JOIN
        MAX_MOV_BY_OTHER_DIRECTORS NMO ON NMY.ACTOR_PID = NMO.ACTOR_PID
)
SELECT
    COUNT(DISTINCT TRIM(P.PID)) AS "Number of actor"
FROM
    Person P
WHERE
    TRIM(P.PID) IN (
        SELECT
            DISTINCT ACTOR_PID
        FROM
            ACTORS_MOV_COMPARISION
        WHERE
            MORE_MOV_BY_YC = 'Y'
    );