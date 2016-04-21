"""
Functions to create the database, populate the db tables and proccess data.

"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database, drop_database
import boto3
import csv
from dateutil.parser import parse
#import resource        print(link_def.id, 'Memory usage: %s (kb)' % int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


from meerkat_abacus import model
from meerkat_abacus import config
from meerkat_abacus.codes import to_codes
from meerkat_abacus import util
from meerkat_abacus.util import create_fake_data
country_config = config.country_config


def create_db(url, base, drop=False):
    """
    The function creates the database

    Args:
        base: An SQLAlchmey declarative base with the db schema
        url : the database_url
        country_config: A contry config dictionary
        drop: Flag to drop the database before creating it

    Returns:
        Boolean: True
    """
    if drop and database_exists(url):
        drop_database(url)
    if not database_exists(url):
        create_database(url)
    engine = create_engine(url)
    base.metadata.create_all(engine)
    return True


def add_fake_data(session, N=500, append=False):
    """
    Creates a csv file with fake data for each form. We make
    sure that the forms have deviceids that match the imported locations.

    For the case report forms we save the X last characters of meta/instanceID to use as alert_ids for 
    the alert_form, where X is the alert_id_lenght from the config file.

    Args:
       session: SQLAlchemy session
       N: number of rows to create for each from (default=500)
       append: If we should append the new fake data or write over the old (default=False)
    """
    deviceids = util.get_deviceids(session, case_report=True)
    alert_ids = []
    forms = list(country_config["tables"].keys())
    # Make sure the case report form is handled before the alert form
    forms.remove("case")
    forms.insert(0, "case")
    for form in forms:
        form_name = country_config["tables"][form]
        file_name = config.data_directory + form_name + ".csv"
        current_form = []
        if append:
            current_form = util.read_csv(file_name)
        if "deviceids" in country_config["fake_data"][form]:
            # This is a special way to limit the deviceids for a form in the config file
            form_deviceids = country_config["fake_data"][form]["deviceids"]
        else:
            form_deviceids = deviceids
        new_data = create_fake_data.create_form(
            country_config["fake_data"][form],
            data={"deviceids": form_deviceids, "uuids": alert_ids}, N=N)
        if form == "case":
            alert_ids = []
            for row in new_data:
                alert_ids.append(
                    row["meta/instanceID"][-country_config["alert_id_length"]:])
        util.write_csv(current_form + new_data, file_name)

        
def get_data_from_s3(bucket):
    """
    Get form data from s3 bucket

    To run, needs to be authenticated with AWS.

    Args: 
       bucket: bucket_name
    """
    s3 = boto3.resource('s3')
    for form in country_config["tables"].values():
        file_name = form + ".csv"
        s3.meta.client.download_file(bucket,
                                     "data/" + file_name,
                                     config.data_directory + file_name)


def table_data_from_csv(filename, table, directory, session,
                        engine, deviceids=None, table_name=None,
                        row_function=None):
    """
    Adds all the data from a csv file. We delete all old data first and then add new data. 
    Args:
        filename: name of table
        table: table class
        directory: directory where the csv file is
        engine: SqlAlchemy engine
        session: SqlAlchemy session
        deviceids: if we should only add rows with a one of the deviceids
        table_name: name of table if different from filename
        row_function: function to appy to the rows before inserting
    """
    session.query(table).delete()
    if not table_name:
        engine.execute("ALTER SEQUENCE {}_id_seq RESTART WITH 1;"
                       .format(filename))
    else:
        engine.execute("ALTER SEQUENCE {}_id_seq RESTART WITH 1;"
                       .format(table_name))
    session.commit()

    for row in util.read_csv(directory + filename + ".csv"):
        if "_index" in row:
            row["index"] = row.pop("_index")
        if row_function:
            insert_row = row_function(row)
        else:
            insert_row = row
        if deviceids:
            if insert_row["deviceid"] in deviceids:
                session.add(table(**{"data": insert_row,
                                     "uuid": insert_row["meta/instanceID"]
                }))
        else:
            session.add(table(**{"data": insert_row,
                                 "uuid": insert_row["meta/instanceID"]}))
    session.commit()


def import_variables(session):
    """
    Import variables from config file

    Args:
       session: db-session
    """
    session.query(model.AggregationVariables).delete()
    session.commit()
    codes_file = config.config_directory + country_config["codes_file"]+".csv"
    for row in util.read_csv(codes_file):
        row.pop("")
        row = util.field_to_list(row, "category")
        session.add(model.AggregationVariables(**row))
    session.commit()


def import_data(engine, session):
    """
    Imports data from csv files for the forms

    Args:
       engine: db engine
       session: db session
    """

    deviceids_case = util.get_deviceids(session, case_report=True)
    deviceids = util.get_deviceids(session)
    for form in model.form_tables.keys():
        if form in ["case", "register"]:
            form_deviceids = deviceids_case
        else:
            form_deviceids = deviceids
        table_data_from_csv(country_config["tables"][form],
                            model.form_tables[form],
                            config.data_directory,
                            session, engine,
                            deviceids=form_deviceids)


def import_links(session):
    """
    Imports all links from links-file

    Args:
        session: db session
    """
    for link in config.links.links:
        session.add(model.LinkDefinitions(**link))
    session.commit()

    
def import_clinics(csv_file, session, country_id):
    """
    import clinics from csv file

    Args:
        csv_file: path to csv file with regions
        session: SQLAlchemy session
        country_id: id of the country
    """

    result = session.query(model.Locations)\
                    .filter(model.Locations.parent_location == country_id)
    regions = {}
    for region in result:
        regions[region.name] = region.id

    districts = {}
    result = session.query(model.Locations)\
                    .filter(model.Locations.parent_location != country_id)
    for district in result:
        districts[district.name] = district.id

    with open(csv_file) as f:
        clinics_csv = csv.DictReader(f)
        for row in clinics_csv:
            if row["deviceid"]:
                if "case_report" in row.keys():
                    if row["case_report"] == "Yes":
                        case_report = 1
                    else:
                        case_report = 0
                else:
                    case_report = 0
                # If the clinic has a district we use that as the parent_location,
                # otherwise we use the region
                if row["district"]:
                    parent_location = districts[row["district"]]
                elif row["region"]:
                    parent_location = regions[row["region"]]
                result = session.query(model.Locations)\
                                .filter(model.Locations.name == row["clinic"],
                                        model.Locations.parent_location == parent_location,
                                        model.Locations.clinic_type != None)

                # If two clinics have the same name and the same parent_location,
                # we are dealing with two tablets from the same clinic, so we
                # combine them.
                if len(result.all()) == 0:
                    if row["longitude"] and row["latitude"]:
                        geolocation = row["latitude"] + "," + row["longitude"]
                    else:
                        geolocation = None
                    session.add(model.Locations(name=row["clinic"],
                                                parent_location=parent_location,
                                                geolocation=geolocation,
                                                deviceid=row["deviceid"],
                                                clinic_type=row["clinic_type"],
                                                case_report=case_report,
                                                level="clinic"))
                else:
                    location = result.first()
                    location.deviceid = location.deviceid + "," + row["deviceid"]
    session.commit()


def import_regions(csv_file, session, parent_id):
    """
    import regions from csv

    Args:
        csv_file: path to csv file with regions
        session: SQLAlchemy session
        parent_id: The id of the country
    """
    with open(csv_file) as f:
        csv_regions = csv.DictReader(f)
        for row in csv_regions:
            session.add(model.Locations(name=row["region"],
                                        parent_location=parent_id,
                                        geolocation=row["geo"],
                                        level="region"))
    session.commit()


def import_districts(csv_file, session):
    """
    import districts from csv

    Args:
        csv_file: path to csv file with regions
        session: SQLAlchemy session
    """
    regions = {}
    for instance in session.query(model.Locations):
        regions[instance.name] = instance.id
    with open(csv_file) as f:
        districts_csv = csv.DictReader(f)
        for row in districts_csv:
            session.add(model.Locations(name=row["district"],
                                        parent_location=regions[row["region"]],
                                        level="district"))
    session.commit()


def import_locations(engine, session):
    """
    Imports all locations from csv-files

    Args:
        engine: SQLAlchemy connection engine
        session: db session
    """
    session.query(model.Locations).delete()
    engine.execute("ALTER SEQUENCE locations_id_seq RESTART WITH 1;")
    session.add(model.Locations(name=country_config["country_name"]))
    session.commit()
    regions_file = (config.config_directory + "locations/" +
                    country_config["locations"]["regions"])
    districts_file = (config.config_directory + "locations/" +
                      country_config["locations"]["districts"])
    clinics_file = (config.config_directory + "locations/" +
                    country_config["locations"]["clinics"])
    import_regions(regions_file, session, 1)
    import_districts(districts_file, session)
    import_clinics(clinics_file, session, 1)


def set_up_everything(leave_if_data, drop_db, N):
    """
    Sets up the db and imports all the data. This should leave 
    the database completely ready to use by the API.

    Args:
        leave_if_data: do nothing if data is there
        drop_db: shall db be dropped before created
        N: number of data points to create
    """
    set_up = True
    if leave_if_data:
        if database_exists(config.DATABASE_URL):
            engine = create_engine(config.DATABASE_URL)
            Session = sessionmaker(bind=engine)
            session = Session()
            if len(session.query(model.Data).all()) > 0:
                set_up = False
    if set_up:
        print("Create DB")
        create_db(config.DATABASE_URL, model.Base, drop=drop_db)
        engine = create_engine(config.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        print("Import Locations")
        import_locations(engine, session)
        if config.fake_data:
            print("Generate fake data")
            add_fake_data(session, N=N, append=False)
        if config.get_data_from_s3:
            print("Get data from s3")
            get_data_from_s3(config.s3_bucket)
        print("Import Data")
        import_data(engine, session)
        print("Import Variables")
        import_variables(session)
        print("Import Links")
        import_links(session)
        print("To codes")
        session.query(model.Data).delete()
        engine.execute("ALTER SEQUENCE data_id_seq RESTART WITH 1;")
        session.commit()
        new_data_to_codes(engine)
        print("Add Links")
        session.query(model.Links).delete()
        engine.execute("ALTER SEQUENCE links_id_seq RESTART WITH 1;")
        session.commit()
        add_new_links()
    return set_up

def import_new_data():
    """
    Import new data from csv files 
    """
    engine = create_engine(config.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    for form in model.form_tables.keys():
        file_path = config.data_directory + country_config["tables"][form] + ".csv"
        data = util.read_csv(file_path)
        new = add_new_data(form, model.form_tables[form],
                                data, session)
    return True


def add_new_data(form_name, form, data, session):
    """
    adds rows in data that has a uuid not already in the form

    Args:
        form_name: type of form, case, register etc
        form: form to add to
        data: data to potentially be added
        session: db session

    Returns:
        new_rows(list): a list of rows added
    """
    result = session.query(form.uuid)
    uuids = []
    deviceids_case = util.get_deviceids(session, case_report=True)
    deviceids = util.get_deviceids(session)
    for r in result:
        uuids.append(r.uuid)
    new_rows = []
    for row in data:
        if row["meta/instanceID"] not in uuids:
            add = False
            if form_name in ["case", "register"]:
                if row["deviceid"] in deviceids_case:
                    add = True
            else:
                if row["deviceid"] in deviceids:
                    add = True
            if add:
                session.add(form(uuid=row["meta/instanceID"], data=row))
                new_rows.append(row)
    session.commit()
    return new_rows


def add_new_fake_data(to_add):
    """
    add new fake data

    Args:
       to_add: number of new records to add
    """
    engine = create_engine(config.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    add_fake_data(session, to_add, append=True)


def new_data_to_codes(engine=None, no_print=False):
    """
    Run all the raw data through the to_codes function to translate it into structured data

    Args: 
        engine: db engine

    """
    if not engine: 
        engine = create_engine(config.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    variables = to_codes.get_variables(session)
    locations = util.all_location_data(session)
    old_data = session.query(model.Data.uuid)
    uuids = []
    alerts = []
    
    for row in old_data:
        uuids.append(row.uuid)
    for form in model.form_tables.keys():
        result = session.query(model.form_tables[form].uuid,
                               model.form_tables[form].data).yield_per(500)
        i = 0
        for row in result:
            if row.uuid not in uuids:
                new_data, alert = to_codes.to_code(
                    row.data,
                    variables,
                    locations,
                    country_config["form_dates"][form],
                    country_config["tables"][form],
                    country_config["alert_data"])
                if new_data and new_data.variables != {}:
                    session.add(new_data)
                if alert:
                    alerts.append(alert)
            i += 1
            if i % 100 == 0 and not no_print:
                print(i)
    add_alerts(alerts, session)
    session.commit()
    return True

def add_new_links():
    """
    add new links

    0. Get all old Links
    For each type of link we perform the following steps:
    1. We construct the conditions on the from table and get the from records
    2. Loop through all the from records and create the link_from_values dict
         with row[from_key] = row
    3. Then we sort out the to conditions and get all the to records
    4. We loop through the to records and find all the to-from matches
    5. We then check if an old link exist and then use the link rule to update the old link,
        most links always take the latest record and use it as the link
    6. Prepare link data and add the link

    Most of the complexity in the function comes from dealing with the difference between 
    form tables and other tables. 

    """

    engine = create_engine(config.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    link_defs = util.get_link_definitions(session)
    results = session.query(model.Links)
    #Get Old links
    to_ids = []
    links_by_link_value = {}
    for links_def_id in link_defs:
        links_by_link_value[links_def_id] = {}
    for row in results:
        to_ids.append(row.to_id)
        links_by_link_value[row.link_def][row.link_value] = row
        
    for link_def_id in link_defs.keys():
        link_def = link_defs[link_def_id]
        if "form_tables." in link_def.from_table:
            table = link_def.from_table.split(".")[1]
            from_table = model.form_tables[table]
        else:
            from_table = getattr(model, link_def.from_table)
        #Sort out from table conditions and get from records
        if link_def.from_condition:
            if ":" in link_def.from_condition:
                column, condition = link_def.from_condition.split(":")
                link_from = session.query(from_table)
                if "form_tables." in link_def.from_table:
                    query_condition = [from_table.data[column].astext == condition,
                                       from_table.data[link_def.from_column].astext != None]
                else:
                    query_condition = [getattr(from_table,column) == condition,
                                       getattr(from_table,link_def.from_column) != None]
                link_from = session.query(from_table).filter(*query_condition).yield_per(200)
            else:
                raise NameError
        else:
                link_from = session.query(from_table).yield_per(200)
        link_from_values = {} # row[from_key] = row dict
        for row in link_from:
            if "form_tables." in link_def.from_table:
                if link_def.from_column in row.data:
                    value = row.data[link_def.from_column]
                else:
                    continue
            else:
                value = getattr(row, link_def.from_column)
            if link_def.compare_lower:
                value = value.lower()
            link_from_values[value] = row
        #Sort out to_conditions
        if link_def.to_condition:
            if ":" in link_def.to_condition:
                column, condition = link_def.to_condition.split(":")
                result_to_table = session.query(model.form_tables[link_def.to_table]).filter(
                    model.form_tables[link_def.to_table].data[column].astext == condition).yield_per(200)
            else:
                raise NameError
        else:
            result_to_table = session.query(model.form_tables[link_def.to_table]).filter(
                model.form_tables[link_def.to_table].data.has_key(link_def.to_column),
                model.form_tables[link_def.to_table].data[link_def.to_column] != None ).yield_per(200)
        for row in result_to_table:
            if row.uuid not in to_ids and link_def.to_column in row.data:
                link_to_value = row.data[link_def.to_column]
                if link_def.compare_lower:
                    link_to_value = link_to_value.lower()
                if link_to_value and link_to_value in link_from_values.keys():
                    data = prepare_link_data(link_def.data, row.data)
                    linked_record = link_from_values[link_to_value]
                    to_date = parse(row.data[link_def.to_date])
                    if link_to_value in links_by_link_value[link_def_id].keys():
                        old_link = links_by_link_value[link_def_id][link_to_value]
                        if link_def.which == "last" and old_link.to_date <= to_date:
                            old_link.data = data
                            old_link.to_date = to_date
                            old_link.to_id = getattr(row, "uuid"),
                    else:
                        if "form_tables." in link_def.from_table:
                            from_date = linked_record.data[link_def.from_date]
                        else:
                            from_date = getattr(linked_record,
                                                 link_def.from_date)
                            
                        new_link = model.Links(**{
                            "link_value": link_to_value,
                            "to_id": getattr(row, "uuid"),
                            "to_date": to_date,
                            "from_date": from_date,
                            "link_def": link_def_id,
                            "data": data})
                        links_by_link_value[link_def_id][link_to_value] = new_link
                        session.add(new_link)
    session.commit()
    return True


def prepare_link_data(data_def, row):
    """
    Returns row translated to data after data_def in the link
    For each key, value pair in data_def we will return a predetermined value based on data in row.
    
    Example of data_def
    {
    "status": {
      "Ongoing": {"column": "alert_labs./return_lab",
                  "condition": ["", "unsure"]},
      "Confirmed": {"column": "alert_labs./return_lab",
                    "condition": "yes"},
      "Disregarded": {"column": "alert_labs./return_lab",
                       "condition": "no"}
      }}

    So for each key(here "status") we want to determine which of the values 
    (here: "Ongoing", "Confirmed", "Disregarded") apply for a given row. 

    We loop through the options and check which applies. If more than one applies we 
    return a list of those options. 
    
    Each option has a column and a condition. If the condition is a list, row[column] can match any of the listed conditions. 
    If the condition is "default_value", that option is always added. 
    
    Args:
        data_def: dictionary with data definition
        row: a row to be translated
    Returns:
        data(dict): the data
    """
    data = {}
    for key in data_def.keys():
        data[key] = []
        default = None
        for value in data_def[key].keys():
            value_dict = data_def[key][value]
            # We can set a default value, if no other value is set
            if data_def[key][value]["condition"] == "default_value":
                default = value
                continue
            if isinstance(data_def[key][value]["column"], list):
                for c in data_def[key][value]["column"]:
                    if row[c] == value_dict["condition"]:
                        data[key].append(value)
                        break
            else:
                if isinstance(data_def[key][value]["condition"], list):
                    if value_dict["column"] in row and row[value_dict["column"]] in value_dict["condition"]:
                        data[key].append(value)
                else:
                    if value_dict["condition"] == "get_value":
                        data[key].append(row.get(value_dict["column"], None))
                    elif value_dict["column"] in row and value_dict["condition"] in row[value_dict["column"]].split(","):
                        data[key].append(value)

        if len(data[key]) == 1:
            data[key] = data[key][0]
        elif len(data[key]) == 0 and default:
            data[key] = default
    return data


def add_alerts(alerts, session):
    """
    Inserts all the alerts. and call the send_alert function
    Args:
        alerts: list of alerts
        session: db session
    """
    locations = util.get_locations(session)
    variables = util.get_variables(session)
    for alert in alerts:
        alert.id = alert.uuids[-country_config["alert_id_length"]:]
        util.send_alert(alert, variables, locations)
        session.add(alert)
    session.commit()
