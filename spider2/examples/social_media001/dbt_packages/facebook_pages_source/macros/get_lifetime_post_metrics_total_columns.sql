{% macro get_lifetime_post_metrics_total_columns() %}

{% set columns = [
    {"name": "_fivetran_synced", "datatype": dbt.type_timestamp()},
    {"name": "date", "datatype": dbt.type_timestamp()},
    {"name": "post_clicks", "datatype": dbt.type_int()},
    {"name": "post_engaged_fan", "datatype": dbt.type_int()},
    {"name": "post_engaged_users", "datatype": dbt.type_int()},
    {"name": "post_id", "datatype": dbt.type_string()},
    {"name": "post_impressions", "datatype": dbt.type_int()},
    {"name": "post_impressions_fan", "datatype": dbt.type_int()},
    {"name": "post_impressions_nonviral", "datatype": dbt.type_int()},
    {"name": "post_impressions_organic", "datatype": dbt.type_int()},
    {"name": "post_impressions_paid", "datatype": dbt.type_int()},
    {"name": "post_impressions_viral", "datatype": dbt.type_int()},
    {"name": "post_negative_feedback", "datatype": dbt.type_int()},
    {"name": "post_reactions_anger_total", "datatype": dbt.type_int()},
    {"name": "post_reactions_haha_total", "datatype": dbt.type_int()},
    {"name": "post_reactions_like_total", "datatype": dbt.type_int()},
    {"name": "post_reactions_love_total", "datatype": dbt.type_int()},
    {"name": "post_reactions_sorry_total", "datatype": dbt.type_int()},
    {"name": "post_reactions_wow_total", "datatype": dbt.type_int()},
    {"name": "post_video_avg_time_watched", "datatype": dbt.type_int()},
    {"name": "post_video_complete_views_30_s_autoplayed", "datatype": dbt.type_int()},
    {"name": "post_video_complete_views_30_s_clicked_to_play", "datatype": dbt.type_int()},
    {"name": "post_video_complete_views_30_s_organic", "datatype": dbt.type_int()},
    {"name": "post_video_complete_views_30_s_paid", "datatype": dbt.type_int()},
    {"name": "post_video_complete_views_organic", "datatype": dbt.type_int()},
    {"name": "post_video_complete_views_paid", "datatype": dbt.type_int()},
    {"name": "post_video_length", "datatype": dbt.type_int()},
    {"name": "post_video_view_time", "datatype": dbt.type_int()},
    {"name": "post_video_view_time_organic", "datatype": dbt.type_int()},
    {"name": "post_video_views", "datatype": dbt.type_int()},
    {"name": "post_video_views_10_s", "datatype": dbt.type_int()},
    {"name": "post_video_views_10_s_autoplayed", "datatype": dbt.type_int()},
    {"name": "post_video_views_10_s_clicked_to_play", "datatype": dbt.type_int()},
    {"name": "post_video_views_10_s_organic", "datatype": dbt.type_int()},
    {"name": "post_video_views_10_s_paid", "datatype": dbt.type_int()},
    {"name": "post_video_views_10_s_sound_on", "datatype": dbt.type_int()},
    {"name": "post_video_views_15_s", "datatype": dbt.type_int()},
    {"name": "post_video_views_autoplayed", "datatype": dbt.type_int()},
    {"name": "post_video_views_clicked_to_play", "datatype": dbt.type_int()},
    {"name": "post_video_views_organic", "datatype": dbt.type_int()},
    {"name": "post_video_views_paid", "datatype": dbt.type_int()},
    {"name": "post_video_views_sound_on", "datatype": dbt.type_int()}
] %}

{{ return(columns) }}

{% endmacro %}