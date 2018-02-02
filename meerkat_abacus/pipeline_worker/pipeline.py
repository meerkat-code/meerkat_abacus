"""
Main pipeline for abacus

"""
import logging

from meerkat_abacus.pipeline_worker.process_steps.quality_control import QualityControl
from meerkat_abacus.pipeline_worker.process_steps.write_to_db import WriteToDb
from meerkat_abacus.pipeline_worker.process_steps import DoNothing


class Pipeline:
    """
    Creates and then runs data through a pipeline as specifed by
    config object

    """
    def __init__(self, engine, session, param_config):
        pipeline_spec = param_config.country_config["pipeline"]
        pipeline = []

        for step in pipeline_spec:
            if step == "do_nothing":
                pipeline.append(DoNothing())
            if step == "quality_control":
                pipeline.append(
                    QualityControl(
                        session,
                        param_config
                    )
                )
                    
            if step == "write_to_db":
                pipeline.append(
                    WriteToDb(
                        param_config,
                        engine
                    )
                )
       
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
            new_data = []
            for d in data:
                data = d["data"]
                form = d["form"]
                new_data += step.run(form, data)
            if not new_data:
                break
            data = new_data
        return data


























### CODE that will be needed again soon


              #   variables[form] = to_codes.get_variables(session
        #                                              match_on_form=data_type["form"])
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
#             logging.exception("Error in process buffer", exc_info=True)
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
#     logging.info(end)
#     qc_m = statistics.mean(qc)
#     initial_visit_m = statistics.mean(initial_visit)
#     first_db_write_m = statistics.mean(first_db_write)
#     to_data_m = statistics.mean(to_data)
#     second_db_write_m = statistics.mean(second_db_write)
#     logging.info(f"{qc_m}, {initial_visit_m}, {first_db_write_m}, {to_data_m}, {second_db_write_m}")
#     import sys
#     sys.exit()
# import statistics
