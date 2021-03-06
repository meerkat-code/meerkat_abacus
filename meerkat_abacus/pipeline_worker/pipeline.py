"""
Main pipeline for abacus

"""
import datetime

from meerkat_abacus import model
from meerkat_abacus.pipeline_worker.process_steps.quality_control import QualityControl
from meerkat_abacus.pipeline_worker.process_steps.write_to_db import WriteToDb
from meerkat_abacus.pipeline_worker.process_steps.add_links import AddLinks
from meerkat_abacus.pipeline_worker.process_steps.to_codes import ToCodes
from meerkat_abacus.pipeline_worker.process_steps.send_alerts import SendAlerts
from meerkat_abacus.pipeline_worker.process_steps.add_multiple_alerts import AddMultipleAlerts
from meerkat_abacus.pipeline_worker.process_steps.to_data_type import ToDataType
from meerkat_abacus.pipeline_worker.process_steps.initial_visit_control import InitialVisitControl
from meerkat_abacus.pipeline_worker.process_steps import DoNothing
from meerkat_abacus import logger



class Pipeline:
    """
    Creates and then runs data through a pipeline as specifed by
    config object

    """
    def __init__(self, engine, session, param_config):
        pipeline_spec = param_config.country_config["pipeline"]
        pipeline = []
        step_args = (param_config, session)
        for step_name in pipeline_spec:
            if step_name == "do_nothing":
                step_ = DoNothing(session)
            elif step_name == "quality_control":
                step_ = QualityControl(*step_args)
            elif step_name == "write_to_db":
                step_ = WriteToDb(*step_args)
                step_.engine = engine
            elif step_name == "initial_visit_control":
                step_ = InitialVisitControl(*step_args)
                step_.engine = engine
            elif step_name == "to_data_type":
                step_ = ToDataType(*step_args)
            elif step_name == "add_links":
                step_ = AddLinks(*step_args)
                step_.engine = engine
            elif step_name == "to_codes":
                step_ = ToCodes(*step_args)
            elif step_name == "send_alerts":
                step_ = SendAlerts(*step_args)
            elif step_name == "add_multiple_alerts":
                step_ = AddMultipleAlerts(*step_args)
                step_.engine = engine
            else:
                raise NotImplementedError(f"Step '{step_name}' is not implemented")
            pipeline.append(step_)
        self.session = session
        self.engine = engine
        self.param_config = param_config
        self.pipeline = pipeline
        self.param_config = param_config

    def process_chunk(self, input_data):
        """
        Processing a chunk of data from the internal buffer


        Each step in this pipeline should take a single record and return
        data = input_data
     
        """
        data = input_data
        for step in self.pipeline:
            step.start_step()
            n = len(data)
            new_data = []
            for d in data:
                data_field = d["data"]
                form = d["form"]
                try:
                    new_data += step.run(form, data_field)
                except Exception as exception:
                    self.handle_exception(d, exception, step)
                    n = n - 1
            step.end_step(n)
            data = new_data
            if not new_data:
                break
        return data

    def handle_exception(self, data, exception, step):
        """
        Handles an exeption in the step.run method by writing the data
        to a log table and logging the exception
        """
        form_data = data["data"]
        form = data["form"]
        logger.exception(f"There was an error in step {step}", exc_info=True)
        self.session.rollback()
        error_str = type(exception).__name__ + ": " + str(exception)
        self.session.add(
            model.StepFailiure(
                data=fix_json(form_data),
                form=form,
                step_name=str(step),
                error=error_str
                )
            )
        self.session.commit()


def fix_json(row):
    for key, value in row.items():
        if isinstance(value, datetime.datetime):
            row[key] = value.isoformat()


#### ALERT CODE
#  if "alert" in variable_data:
#                variable_data["alert_id"] = row[data_type["form"]][data_type[
#                    "uuid"]][-param_config.country_config["alert_id_length"]:]


 # if "alert" in variable_data and not disregard:
 #                alerts = session.query(model.AggregationVariables).filter(
 #                    model.AggregationVariables.alert == 1)
 #                alert_variables = {a.id: a for a in alerts}

 #                alert_id = new_data["uuid"][-param_config.country_config["alert_id_length"]:]
 #                util.send_alert(alert_id, new_data,
 #                                alert_variables, locations[0], param_config)















### CODE that will be needed again soon


              #   
        # self.quality_control_arguments = quality_control_arguments

        # self.locations = util.all_location_data(session)
        # self.links = util.get_links(param_config.config_directory +
        #                     param_config.country_config["links_file"]) 
#         uuids = []
#         tables = defaultdict(list)
#         for data_row in input_data:
#             data = data_row["data"]
#             form = data_row["form"]
#             data = data_import.quality_control(
#                 form,
#                 data,
#                 **self.quality_control_arguments)
#             if not data:
#                 continue
#             #consul.flush_dhis2_events()
#             corrected = data_management.initial_visit_control(
#                 form,
#                 data,
#                 self.engine,
#                 self.session,
#                 param_config=self.param_config
#             )
#         initial_visit.append(time.time() - s)
#         s = time.time()
#         insert_data = []
#         for row in corrected:
#             insert_data.append({
#                 "uuid": row[kwargs["uuid_field"]],
#                 "data": row}
#             )

#         #consul.send_dhis2_events(uuid=data[kwargs["uuid_field"],
#         #                         form_id=corrected,
#         #                         raw_row=data)

#         try:
#             table = model.form_tables(param_config=param_config)[form]
#         except KeyError:
#             logger.exception("Error in process buffer", exc_info=True)
#             continue
        
#         write_to_db(engine, insert_data, table=table)
#         first_db_write.append(time.time() - s)
#         s = time.time()
#         data = []
#         disregarded = []
#         data_types = []
#         for row in corrected:
#             data_i, disregarded_i, data_types_i = data_management.new_data_to_codes(
#                 form,
#                 row,
#                 row[kwargs["uuid_field"]],
#                 locations,
#                 links,
#                 variables,
#                 session,
#                 engine,
#                 debug_enabled=True,
#                 param_config=param_config,
#             )
#             data += data_i
#             disregarded += disregarded_i
#             data_types += data_types_i
#         to_data.append(time.time() - s)
#         s = time.time()
#         for i in range(len(data)):
#             write_to_db(engine, data[i],
#                         table=[model.Data, model.DisregardedData][disregarded[i]],
#                         delete=("type", data_types[i]))
#         second_db_write.append(time.time() - s)
#         data_management.add_alerts(session, data, 
#                                    param_config=param_config)

        
#     end = time.time() - start #after_insert - after_qc - start
#     logger.info(end)
#     qc_m = statistics.mean(qc)
#     initial_visit_m = statistics.mean(initial_visit)
#     first_db_write_m = statistics.mean(first_db_write)
#     to_data_m = statistics.mean(to_data)
#     second_db_write_m = statistics.mean(second_db_write)
#     logger.info(f"{qc_m}, {initial_visit_m}, {first_db_write_m}, {to_data_m}, {second_db_write_m}")
#     import sys
#     sys.exit()
# import statistics
