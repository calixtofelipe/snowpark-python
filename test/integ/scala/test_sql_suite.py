#
# Copyright (c) 2012-2021 Snowflake Computing Inc. All right reserved.
#

from test.utils import Utils

import pytest

from snowflake.connector import ProgrammingError
from snowflake.snowpark.functions import col
from snowflake.snowpark.row import Row
from snowflake.snowpark.types.sf_types import LongType, StructField, StructType


def test_non_select_queries(session_cnx, db_parameters):
    with session_cnx(db_parameters) as session:
        try:
            stage_name = Utils.random_name()
            Utils.create_stage(session, stage_name)
            res = session.sql(f"show stages like '{stage_name}'").collect()
            assert len(res) == 1
            # verify result is not empty
            assert f"{stage_name}" in str(res[0])

            table_name1 = Utils.random_name()
            Utils.create_table(session, table_name1, "num int")
            res = session.sql(f"show tables like '{table_name1}'").collect()
            assert len(res) == 1
            # verify result is not empty
            assert f"{table_name1}" in str(res[0])

            res = session.sql("alter session set lock_timeout = 3600").collect()
            assert len(res) == 1
            # verify result is not empty
            assert "Statement executed successfully" in str(res[0])

        finally:
            Utils.drop_stage(session, stage_name)
            Utils.drop_table(session, table_name1)


def test_run_sql_query(session_cnx, db_parameters):
    with session_cnx(db_parameters) as session:
        df1 = session.sql("select * from values (1),(2),(3)")
        assert df1.collect() == [Row(1), Row(2), Row(3)]

        df2 = session.sql(
            "select variance(a) from values(1,1),(1,2),(2,1),(2,2),(3,1),(3,2) as T(a,b)"
        )
        assert str(df2.collect()[0][0]) == "0.800000"

        df3 = session.sql("select * from values (1),(2),(3) as T(id)").filter(
            col("id") < 3
        )
        assert df3.collect() == [Row(1), Row(2)]

        df4 = session.sql("select * from values (1,1),(2,1),(3,1) as T(a,b)")
        df5 = session.sql("select * from values (1,2),(2,2),(3,2) as T(a,b)")
        df6 = df4.union(df5).filter(col("a") < 3)

        res = df6.collect()
        res.sort(key=lambda x: (x[0], x[1]))
        assert res == [Row([1, 1]), Row([1, 2]), Row([2, 1]), Row([2, 2])]

        with pytest.raises(ProgrammingError) as ex_info:
            session.sql("select * from (1)").collect()

        with pytest.raises(ProgrammingError) as ex_info:
            session.sql("select sum(a) over () from values 1.0, 2.0 T(a)").collect()


def test_create_table(session_cnx, db_parameters):
    with session_cnx(db_parameters) as session:
        table_name = Utils.random_name()
        other_name = Utils.random_name()
        try:
            table = session.sql(f"create or replace table {table_name} (num int)")
            assert len(table.schema.fields) > 0

            # assert the table is not created before collect
            with pytest.raises(ProgrammingError) as ex_info:
                session.sql(f"select from {table_name}").collect()

            table.collect()

            # drop table
            drop_table = session.sql(f"drop table {table_name}")
            assert len(drop_table.schema.fields) > 0
            drop_table.collect()
            # assert that the table is already dropped
            with pytest.raises(ProgrammingError) as ex_info:
                session.sql(f"select * from {table}").collect()

            # test when create/drop table fails
            # throws exception during prepare
            session.sql(f"create or replace table {other_name}")
            with pytest.raises(ProgrammingError) as ex_info:
                session.sql(f"create or replace table {other_name}").collect()
            session.sql(f"drop table {other_name}")
            with pytest.raises(ProgrammingError) as ex_info:
                session.sql(f"drop table {other_name}").collect()

        finally:
            Utils.drop_table(session, table_name)
            Utils.drop_table(session, other_name)


def test_insert_into_table(session_cnx, db_parameters):
    with session_cnx(db_parameters) as session:
        table_name1 = Utils.random_name()
        table_name2 = Utils.random_name()
        try:
            Utils.create_table(session, table_name1, "num int")
            insert = session.sql(f"insert into {table_name1} values(1),(2),(3)")

            # TODO uncomment - once Connector bug is fixed
            # expected_schema = StructType([StructField("\"number of rows inserted\"",
            #                                          LongType(), nullable=False)])
            # assert insert.schema() == expected_schema
            insert.collect()
            df = session.sql(f"select * from {table_name1}")
            assert df.collect() == [Row(1), Row(2), Row(3)]

            # test for insertion to a non-existing table
            # no error
            session.sql(f"insert into {table_name2} values(1),(2),(3)")
            with pytest.raises(ProgrammingError):
                session.sql(f"insert into {table_name2} values(1),(2),(3)").collect()

            # test for insertion with wrong type of data, throws exception when collect
            insert2 = session.sql(f"insert into {table_name1} values(1.4),('test')")
            with pytest.raises(ProgrammingError):
                insert2.collect()

        finally:
            Utils.drop_table(session, table_name1)
            Utils.drop_table(session, table_name2)


def test_show(session_cnx, db_parameters):
    with session_cnx(db_parameters) as session:
        table_name = Utils.random_name()
        try:
            Utils.create_table(session, table_name, "num int")
            table_sql_res = session.sql("SHOW TABLES")
            res = table_sql_res.collect()
            assert len(res) > 0
        finally:
            Utils.drop_table(session, table_name)

        # test when input is a wrong show command, throws exception when prepare
        # no error
        session.sql("SHOW TABLE")
        with pytest.raises(ProgrammingError):
            session.sql("SHOW TABLE").collect()