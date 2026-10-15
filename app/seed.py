"""Synthetic City Infrastructure Seeder for Ripple City.

Generates an interconnected municipal infrastructure network with cross-sector dependencies:
Substations -> WaterPumps -> MobileTowers -> Hospitals & Clinics -> EmergencyCenters -> Roads -> BackupGenerators.
Also includes InfrastructureZones and persistent Incident Memory (Incident, RecoveryAction, EvidenceRecord).

Uses Cypher MERGE commands for 100% idempotent execution without data duplication.
"""

import logging
from typing import Optional
from app.db import FalkorDBClient, db_client
from app.schema import (
    EntityType,
    Criticality,
    OperationalStatus,
    RelationshipType,
    InfrastructureNodeData,
    RelationshipData,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Synthetic Infrastructure Zones (5 Zones)
# ---------------------------------------------------------------------------
SYNTHETIC_ZONES = [
    InfrastructureNodeData(
        id="ZONE-DTN",
        name="Downtown Civic & Commercial Core",
        entity_type=EntityType.ZONE,
        criticality=Criticality.TIER_1_CRITICAL,
        status=OperationalStatus.OPERATIONAL,
        zone="Downtown",
        latitude=40.7128,
        longitude=-74.0060,
        notes="High-density urban center housing financial, governmental, and primary healthcare institutions."
    ),
    InfrastructureNodeData(
        id="ZONE-NR",
        name="North River Healthcare & Residential District",
        entity_type=EntityType.ZONE,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="North River",
        latitude=40.7589,
        longitude=-73.9851,
        notes="Residential corridor featuring specialized cardiac and pediatric healthcare facilities."
    ),
    InfrastructureNodeData(
        id="ZONE-EST",
        name="Eastside Dense Urban & Community Sector",
        entity_type=EntityType.ZONE,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="Eastside",
        latitude=40.7282,
        longitude=-73.9442,
        notes="Mixed residential and light manufacturing district with community outpatient facilities."
    ),
    InfrastructureNodeData(
        id="ZONE-HBR",
        name="Harbor Maritime & Port Logistics Zone",
        entity_type=EntityType.ZONE,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="Harbor",
        latitude=40.6892,
        longitude=-74.0445,
        notes="Deepwater port, maritime freight handling, fuel depots, and coastal rescue base."
    ),
    InfrastructureNodeData(
        id="ZONE-WST",
        name="West Industrial Corridor & Utilities",
        entity_type=EntityType.ZONE,
        criticality=Criticality.TIER_1_CRITICAL,
        status=OperationalStatus.OPERATIONAL,
        zone="West Industrial",
        latitude=40.7410,
        longitude=-74.0320,
        notes="Heavy industrial hub containing central wastewater and regional water purification works."
    ),
]

# ---------------------------------------------------------------------------
# 2. Synthetic Infrastructure Nodes Catalog (51 Physical Assets)
# Total Infrastructure Nodes = 5 Zones + 51 Assets = 56 Nodes
# ---------------------------------------------------------------------------
SYNTHETIC_NODES: list[InfrastructureNodeData] = [
    # ---------------------------------------------------------
    # Substations (Power Transmission Backbone)
    # ---------------------------------------------------------
    InfrastructureNodeData(
        id="SUB-001",
        name="Metro Central Substation",
        entity_type=EntityType.SUBSTATION,
        criticality=Criticality.TIER_1_CRITICAL,
        status=OperationalStatus.OPERATIONAL,
        zone="Downtown",
        latitude=40.7128,
        longitude=-74.0060,
        buffer_hours=0.0,
        capacity_rating="230kV / 450MW",
        notes="Primary downtown grid hub. Direct upstream feeder to water, communications, 911 dispatch, and expressway signaling."
    ),
    InfrastructureNodeData(
        id="SUB-002",
        name="North River Substation",
        entity_type=EntityType.SUBSTATION,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="North River",
        latitude=40.7589,
        longitude=-73.9851,
        buffer_hours=0.0,
        capacity_rating="115kV / 220MW",
        notes="Secondary grid feeder with auxiliary tie-line connecting to TOWER-001 in Downtown."
    ),
    InfrastructureNodeData(
        id="SUB-003",
        name="Eastside Grid Substation",
        entity_type=EntityType.SUBSTATION,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="Eastside",
        latitude=40.7282,
        longitude=-73.9442,
        buffer_hours=0.0,
        capacity_rating="115kV / 180MW",
        notes="Supplies Eastside water booster pumps, clinics, and transit corridor signaling."
    ),
    InfrastructureNodeData(
        id="SUB-004",
        name="Harbor Gateway Substation",
        entity_type=EntityType.SUBSTATION,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="Harbor",
        latitude=40.6892,
        longitude=-74.0445,
        buffer_hours=0.0,
        capacity_rating="115kV / 200MW",
        notes="Feeds container terminal cranes, marine cooling loops, and Coast Guard communications."
    ),
    InfrastructureNodeData(
        id="SUB-005",
        name="West Industrial Heavy Grid",
        entity_type=EntityType.SUBSTATION,
        criticality=Criticality.TIER_1_CRITICAL,
        status=OperationalStatus.OPERATIONAL,
        zone="West Industrial",
        latitude=40.7410,
        longitude=-74.0320,
        buffer_hours=0.0,
        capacity_rating="230kV / 400MW",
        notes="Heavy transmission substation powering the Regional Central Water Treatment Plant."
    ),
    InfrastructureNodeData(
        id="SUB-006",
        name="West Switching Substation",
        entity_type=EntityType.SUBSTATION,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="West Industrial",
        latitude=40.7450,
        longitude=-74.0380,
        buffer_hours=0.0,
        capacity_rating="69kV / 100MW",
        notes="Secondary distribution substation for freight rail interchange and chemical storage."
    ),

    # ---------------------------------------------------------
    # Water Pumps & Treatment (Water Sector)
    # ---------------------------------------------------------
    InfrastructureNodeData(
        id="PUMP-001",
        name="Downtown Water Pumping Station #1",
        entity_type=EntityType.WATER_PUMP,
        criticality=Criticality.TIER_1_CRITICAL,
        status=OperationalStatus.OPERATIONAL,
        zone="Downtown",
        latitude=40.7145,
        longitude=-74.0082,
        buffer_hours=2.5,
        capacity_rating="45 MGD (requires 3.0 MW electrical load)",
        notes="High-pressure pumps feeding St. Jude Hospital chillers and sterilizers. Relies on SUB-001."
    ),
    InfrastructureNodeData(
        id="PUMP-002",
        name="Financial District Booster Pump",
        entity_type=EntityType.WATER_PUMP,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="Downtown",
        latitude=40.7090,
        longitude=-74.0110,
        buffer_hours=1.0,
        capacity_rating="15 MGD",
        notes="Maintains pressure in southern Downtown; has secondary link to regional pipeline."
    ),
    InfrastructureNodeData(
        id="PUMP-003",
        name="North Reservoir Lift Station",
        entity_type=EntityType.WATER_PUMP,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="North River",
        latitude=40.7610,
        longitude=-73.9820,
        buffer_hours=4.0,
        capacity_rating="30 MGD",
        notes="Primary potable water and fire flow provider for North Memorial Hospital."
    ),
    InfrastructureNodeData(
        id="PUMP-004",
        name="Highland Hills Pressure Station",
        entity_type=EntityType.WATER_PUMP,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="North River",
        latitude=40.7650,
        longitude=-73.9790,
        buffer_hours=2.0,
        capacity_rating="18 MGD",
        notes="Elevation booster for northern residential communities."
    ),
    InfrastructureNodeData(
        id="PUMP-005",
        name="Eastside Booster Pump #1",
        entity_type=EntityType.WATER_PUMP,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="Eastside",
        latitude=40.7250,
        longitude=-73.9400,
        buffer_hours=1.5,
        capacity_rating="20 MGD",
        notes="Maintains distribution pressure to Eastside clinics and residential corridors."
    ),
    InfrastructureNodeData(
        id="PUMP-006",
        name="Eastside Secondary Distribution Pump",
        entity_type=EntityType.WATER_PUMP,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="Eastside",
        latitude=40.7300,
        longitude=-73.9350,
        buffer_hours=1.0,
        capacity_rating="12 MGD",
        notes="Secondary feeder for community centers and dialysis clinic reverse osmosis."
    ),
    InfrastructureNodeData(
        id="PUMP-007",
        name="Harbor Marine Cooling & Fire Pump",
        entity_type=EntityType.WATER_PUMP,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="Harbor",
        latitude=40.6870,
        longitude=-74.0420,
        buffer_hours=3.0,
        capacity_rating="25 MGD",
        notes="Provides saltwater/freshwater high-volume fire suppression for port fuel tanks."
    ),
    InfrastructureNodeData(
        id="PUMP-008",
        name="Port Water Storage Lift Pump",
        entity_type=EntityType.WATER_PUMP,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="Harbor",
        latitude=40.6910,
        longitude=-74.0470,
        buffer_hours=2.0,
        capacity_rating="15 MGD",
        notes="Supplies potable water to cargo ships and maritime worker facilities."
    ),
    InfrastructureNodeData(
        id="PUMP-009",
        name="Regional Central Water Treatment Plant",
        entity_type=EntityType.WATER_PUMP,
        criticality=Criticality.TIER_1_CRITICAL,
        status=OperationalStatus.OPERATIONAL,
        zone="West Industrial",
        latitude=40.7390,
        longitude=-74.0300,
        buffer_hours=6.0,
        capacity_rating="80 MGD",
        notes="Primary regional water purification facility. Feeds Downtown (PUMP-001) and Harbor (PUMP-007)."
    ),
    InfrastructureNodeData(
        id="PUMP-010",
        name="West Chemical Scrubbing Water Pump",
        entity_type=EntityType.WATER_PUMP,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="West Industrial",
        latitude=40.7430,
        longitude=-74.0350,
        buffer_hours=2.0,
        capacity_rating="25 MGD",
        notes="Cooling and neutralization water supply for chemical manufacturing."
    ),

    # ---------------------------------------------------------
    # Mobile Towers (Communications Backbone)
    # ---------------------------------------------------------
    InfrastructureNodeData(
        id="TOWER-001",
        name="Downtown Telecom Spine Mast",
        entity_type=EntityType.MOBILE_TOWER,
        criticality=Criticality.TIER_1_CRITICAL,
        status=OperationalStatus.OPERATIONAL,
        zone="Downtown",
        latitude=40.7160,
        longitude=-74.0040,
        buffer_hours=3.5,
        capacity_rating="5G / FirstNet Public Safety Hub",
        notes="Crucial telecommunications spine. Carries 911 CAD dispatch, ambulance telemetry to St. Jude, and police radio."
    ),
    InfrastructureNodeData(
        id="TOWER-002",
        name="North Heights Cellular Mast",
        entity_type=EntityType.MOBILE_TOWER,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="North River",
        latitude=40.7550,
        longitude=-73.9890,
        buffer_hours=4.0,
        capacity_rating="4G/5G Public Safety & Commercial",
        notes="Carries telemetry for North Memorial Hospital and radio channel for North River Fire HQ."
    ),
    InfrastructureNodeData(
        id="TOWER-003",
        name="North River Hilltop Relay",
        entity_type=EntityType.MOBILE_TOWER,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="North River",
        latitude=40.7630,
        longitude=-73.9800,
        buffer_hours=3.0,
        capacity_rating="Microwave Line-of-Sight Hub",
        notes="Relay link between North River civic center and regional state police tower."
    ),
    InfrastructureNodeData(
        id="TOWER-004",
        name="Eastside Relay Tower",
        entity_type=EntityType.MOBILE_TOWER,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="Eastside",
        latitude=40.7290,
        longitude=-73.9420,
        buffer_hours=2.0,
        capacity_rating="Microwave Backhaul Hub",
        notes="Telehealth link and municipal radio repeater for Eastside EMS Station 4."
    ),
    InfrastructureNodeData(
        id="TOWER-005",
        name="Harbor Logistics Telemetry Tower",
        entity_type=EntityType.MOBILE_TOWER,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="Harbor",
        latitude=40.6900,
        longitude=-74.0430,
        buffer_hours=4.0,
        capacity_rating="Marine SCADA / AIS / Coast Guard Radio",
        notes="Coordinates harbor vessel traffic and Coast Guard search-and-rescue."
    ),
    InfrastructureNodeData(
        id="TOWER-006",
        name="West Ridge Industrial Communications Mast",
        entity_type=EntityType.MOBILE_TOWER,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="West Industrial",
        latitude=40.7420,
        longitude=-74.0340,
        buffer_hours=3.0,
        capacity_rating="Industrial SCADA & HazMat Radio",
        notes="SCADA telemetry for water treatment and HazMat sensor telemetry."
    ),

    # ---------------------------------------------------------
    # Hospitals (Tier 1 Life Safety Healthcare)
    # ---------------------------------------------------------
    InfrastructureNodeData(
        id="HOSP-001",
        name="St. Jude Metropolitan Trauma Center",
        entity_type=EntityType.HOSPITAL,
        criticality=Criticality.TIER_1_CRITICAL,
        status=OperationalStatus.OPERATIONAL,
        zone="Downtown",
        latitude=40.7180,
        longitude=-74.0010,
        buffer_hours=6.0,
        capacity_rating="Level 1 Trauma / 650 Beds",
        notes="Major regional hospital. Relies on TOWER-001 for ambulance telemetry, PUMP-001 for cooling water, and ROAD-001 for access."
    ),
    InfrastructureNodeData(
        id="HOSP-002",
        name="North Memorial Specialty Hospital",
        entity_type=EntityType.HOSPITAL,
        criticality=Criticality.TIER_1_CRITICAL,
        status=OperationalStatus.OPERATIONAL,
        zone="North River",
        latitude=40.7595,
        longitude=-73.9810,
        buffer_hours=5.0,
        capacity_rating="Level 2 Trauma / 350 Beds",
        notes="Cardiac and pediatric trauma center with onsite emergency generator GEN-003."
    ),

    # ---------------------------------------------------------
    # Clinics (Outpatient, Specialized & Community Healthcare)
    # ---------------------------------------------------------
    InfrastructureNodeData(
        id="CLINIC-001",
        name="Downtown Urgent Care Center",
        entity_type=EntityType.CLINIC,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="Downtown",
        latitude=40.7155,
        longitude=-74.0075,
        buffer_hours=1.0,
        capacity_rating="Outpatient / Urgent Care",
        notes="High-volume walk-in clinic powered by SUB-001."
    ),
    InfrastructureNodeData(
        id="CLINIC-002",
        name="Northside Pediatric & Family Clinic",
        entity_type=EntityType.CLINIC,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="North River",
        latitude=40.7565,
        longitude=-73.9860,
        buffer_hours=2.0,
        capacity_rating="Family Practice / Immunization",
        notes="Community clinic powered by SUB-002."
    ),
    InfrastructureNodeData(
        id="CLINIC-003",
        name="Eastside Community Health Clinic",
        entity_type=EntityType.CLINIC,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="Eastside",
        latitude=40.7265,
        longitude=-73.9455,
        buffer_hours=1.0,
        capacity_rating="Community Health / Vaccine Depot",
        notes="Stores critical refrigerated vaccines. Attached generator GEN-005 is FAILED and unavailable!"
    ),
    InfrastructureNodeData(
        id="CLINIC-004",
        name="Eastside Dialysis Center",
        entity_type=EntityType.CLINIC,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="Eastside",
        latitude=40.7275,
        longitude=-73.9410,
        buffer_hours=1.5,
        capacity_rating="Specialty Dialysis (32 Stations)",
        notes="Requires continuous municipal water pressure from PUMP-005 for reverse osmosis filtration."
    ),
    InfrastructureNodeData(
        id="CLINIC-005",
        name="Harbor Maritime Workers Clinic",
        entity_type=EntityType.CLINIC,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="Harbor",
        latitude=40.6885,
        longitude=-74.0450,
        buffer_hours=1.5,
        capacity_rating="Occupational Health & Emergency First Aid",
        notes="Port worker clinic powered by SUB-004."
    ),
    InfrastructureNodeData(
        id="CLINIC-006",
        name="West Industrial Occupational Health Facility",
        entity_type=EntityType.CLINIC,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="West Industrial",
        latitude=40.7405,
        longitude=-74.0335,
        buffer_hours=2.0,
        capacity_rating="Industrial Trauma Stabilization",
        notes="Chemical burn and industrial accident triage unit powered by SUB-005."
    ),

    # ---------------------------------------------------------
    # Emergency Centers (Command, Fire, Rescue & Dispatch)
    # ---------------------------------------------------------
    InfrastructureNodeData(
        id="EMERG-001",
        name="Ripple City 911 Dispatch & EOC",
        entity_type=EntityType.EMERGENCY_CENTER,
        criticality=Criticality.TIER_1_CRITICAL,
        status=OperationalStatus.OPERATIONAL,
        zone="Downtown",
        latitude=40.7110,
        longitude=-74.0090,
        buffer_hours=8.0,
        capacity_rating="Central 911 EOC Primary Command",
        notes="Municipal emergency operations command. Relies entirely on TOWER-001 for CAD mobile radio dispatch."
    ),
    InfrastructureNodeData(
        id="EMERG-002",
        name="North River Fire & Rescue HQ",
        entity_type=EntityType.EMERGENCY_CENTER,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="North River",
        latitude=40.7570,
        longitude=-73.9870,
        buffer_hours=4.5,
        capacity_rating="Battalion Headquarters",
        notes="First responder staging base for northern districts."
    ),
    InfrastructureNodeData(
        id="EMERG-003",
        name="Eastside EMS Station 4",
        entity_type=EntityType.EMERGENCY_CENTER,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="Eastside",
        latitude=40.7285,
        longitude=-73.9430,
        buffer_hours=3.0,
        capacity_rating="Paramedic Base (6 Ambulances)",
        notes="Dispatches emergency medical response throughout Eastside."
    ),
    InfrastructureNodeData(
        id="EMERG-004",
        name="Harbor Coast Guard & Port Rescue Station",
        entity_type=EntityType.EMERGENCY_CENTER,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="Harbor",
        latitude=40.6865,
        longitude=-74.0460,
        buffer_hours=6.0,
        capacity_rating="Maritime Search & Rescue Base",
        notes="Covers maritime emergencies, port fires, and coastal oil spills."
    ),
    InfrastructureNodeData(
        id="EMERG-005",
        name="West Industrial Hazardous Materials Unit",
        entity_type=EntityType.EMERGENCY_CENTER,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="West Industrial",
        latitude=40.7415,
        longitude=-74.0360,
        buffer_hours=5.0,
        capacity_rating="HazMat Regional Rapid Response",
        notes="Specialized chemical, biological, and industrial fire containment unit."
    ),

    # ---------------------------------------------------------
    # Roads & Arterials (Transportation Corridors)
    # ---------------------------------------------------------
    InfrastructureNodeData(
        id="ROAD-001",
        name="Grand Central Expressway Corridor",
        entity_type=EntityType.ROAD,
        criticality=Criticality.TIER_1_CRITICAL,
        status=OperationalStatus.OPERATIONAL,
        zone="Downtown",
        latitude=40.7150,
        longitude=-74.0050,
        buffer_hours=0.0,
        capacity_rating="Primary Evacuation Route / Smart Arterial",
        notes="Major emergency access highway to St. Jude Trauma Center. Powered smart signals rely on SUB-001."
    ),
    InfrastructureNodeData(
        id="ROAD-002",
        name="Riverfront Boulevard Arterial",
        entity_type=EntityType.ROAD,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="Downtown",
        latitude=40.7170,
        longitude=-74.0030,
        buffer_hours=0.0,
        capacity_rating="4-Lane Surface Arterial",
        notes="GENUINE ALTERNATE ACCESS ROUTE to St. Jude Hospital if Expressway signals fail."
    ),
    InfrastructureNodeData(
        id="ROAD-003",
        name="North River Parkway Connector",
        entity_type=EntityType.ROAD,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="North River",
        latitude=40.7580,
        longitude=-73.9840,
        buffer_hours=0.0,
        capacity_rating="4-Lane Healthcare Corridor",
        notes="Connects North Memorial Hospital to North River Fire & Rescue HQ."
    ),
    InfrastructureNodeData(
        id="ROAD-004",
        name="Highland Ridge Access Road",
        entity_type=EntityType.ROAD,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="North River",
        latitude=40.7620,
        longitude=-73.9810,
        buffer_hours=0.0,
        capacity_rating="Secondary Access Arterial",
        notes="Provides secondary connection to Highland water lift pumps."
    ),
    InfrastructureNodeData(
        id="ROAD-005",
        name="Eastside Avenue Arterial",
        entity_type=EntityType.ROAD,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="Eastside",
        latitude=40.7270,
        longitude=-73.9435,
        buffer_hours=0.0,
        capacity_rating="Major Commercial Arterial",
        notes="Primary route connecting Eastside clinics and EMS station to Downtown."
    ),
    InfrastructureNodeData(
        id="ROAD-006",
        name="Port Access Freight Highway",
        entity_type=EntityType.ROAD,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="Harbor",
        latitude=40.6880,
        longitude=-74.0435,
        buffer_hours=0.0,
        capacity_rating="Heavy Freight Corridor",
        notes="Container transport route connecting container terminals to rail interchange."
    ),
    InfrastructureNodeData(
        id="ROAD-007",
        name="Harbor Shoreline Bypass",
        entity_type=EntityType.ROAD,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="Harbor",
        latitude=40.6850,
        longitude=-74.0480,
        buffer_hours=0.0,
        capacity_rating="2-Lane Coastal Bypass",
        notes="Emergency perimeter route for Coast Guard and fuel depot security."
    ),
    InfrastructureNodeData(
        id="ROAD-008",
        name="West Industrial Beltway",
        entity_type=EntityType.ROAD,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="West Industrial",
        latitude=40.7400,
        longitude=-74.0310,
        buffer_hours=0.0,
        capacity_rating="HazMat Designated Beltway",
        notes="Dedicated evacuation and heavy equipment conduit for West Industrial."
    ),
    InfrastructureNodeData(
        id="ROAD-009",
        name="Rail Freight Corridor Access Road",
        entity_type=EntityType.ROAD,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="West Industrial",
        latitude=40.7440,
        longitude=-74.0370,
        buffer_hours=0.0,
        capacity_rating="Service Access Road",
        notes="Access road for chemical delivery rail interchange."
    ),

    # ---------------------------------------------------------
    # Backup Generators (Emergency Resiliency Assets)
    # ---------------------------------------------------------
    InfrastructureNodeData(
        id="GEN-001",
        name="St. Jude Standby Generator 1",
        entity_type=EntityType.BACKUP_GENERATOR,
        criticality=Criticality.TIER_1_CRITICAL,
        status=OperationalStatus.OPERATIONAL,
        zone="Downtown",
        latitude=40.7182,
        longitude=-74.0012,
        buffer_hours=12.0,
        capacity_rating="2.5 MW Diesel Generator",
        notes="Dedicated onsite generator with 12h diesel fuel reserve for St. Jude ICU and surgery."
    ),
    InfrastructureNodeData(
        id="GEN-002",
        name="Downtown Mobile Auxiliary Power Unit",
        entity_type=EntityType.BACKUP_GENERATOR,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.DEGRADED,
        zone="Downtown",
        latitude=40.7130,
        longitude=-74.0070,
        buffer_hours=8.0,
        capacity_rating="1.2 MW Mobile Trailer (INSUFFICIENT: Pump requires 3.0 MW)",
        notes="INSUFFICIENT CAPACITY: Can only supply 40% load to PUMP-001; unable to sustain hospital chiller water."
    ),
    InfrastructureNodeData(
        id="GEN-003",
        name="North Memorial Hospital Standby Gen",
        entity_type=EntityType.BACKUP_GENERATOR,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="North River",
        latitude=40.7598,
        longitude=-73.9815,
        buffer_hours=10.0,
        capacity_rating="1.8 MW Diesel Generator",
        notes="Onsite emergency power for North Memorial ICU and surgical suites."
    ),
    InfrastructureNodeData(
        id="GEN-004",
        name="Northside Fire Station Backup Gen",
        entity_type=EntityType.BACKUP_GENERATOR,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.OPERATIONAL,
        zone="North River",
        latitude=40.7572,
        longitude=-73.9868,
        buffer_hours=6.0,
        capacity_rating="500 kW Diesel Generator",
        notes="Powers North River Fire & Rescue HQ station alert systems and vehicle bays."
    ),
    InfrastructureNodeData(
        id="GEN-005",
        name="Eastside Clinic Standby Generator",
        entity_type=EntityType.BACKUP_GENERATOR,
        criticality=Criticality.TIER_3_MEDIUM,
        status=OperationalStatus.FAILED,
        zone="Eastside",
        latitude=40.7268,
        longitude=-73.9458,
        buffer_hours=0.0,
        capacity_rating="250 kW Standby Generator (UNAVAILABLE)",
        notes="UNAVAILABLE BACKUP: Starter motor seized during test. Out of commission pending replacement parts."
    ),
    InfrastructureNodeData(
        id="GEN-006",
        name="Harbor Emergency Marine Generator",
        entity_type=EntityType.BACKUP_GENERATOR,
        criticality=Criticality.TIER_2_HIGH,
        status=OperationalStatus.OPERATIONAL,
        zone="Harbor",
        latitude=40.6868,
        longitude=-74.0458,
        buffer_hours=8.0,
        capacity_rating="1.5 MW Marine Diesel Generator",
        notes="Dedicated backup for Harbor Coast Guard & Port Rescue Station command consoles."
    ),
    InfrastructureNodeData(
        id="GEN-007",
        name="Regional Water Treatment Emergency Turbo-Gen",
        entity_type=EntityType.BACKUP_GENERATOR,
        criticality=Criticality.TIER_1_CRITICAL,
        status=OperationalStatus.OPERATIONAL,
        zone="West Industrial",
        latitude=40.7395,
        longitude=-74.0295,
        buffer_hours=24.0,
        capacity_rating="4.0 MW Dual-Fuel Gas Turbine",
        notes="High-capacity backup for Regional Central Water Treatment Plant."
    ),
]

# ---------------------------------------------------------------------------
# 3. Synthetic Relationships Catalog (Dependency Edges)
# ---------------------------------------------------------------------------
SYNTHETIC_RELATIONSHIPS: list[RelationshipData] = [
    # ---------------------------------------------------------
    # Power feeds from SUB-001 (Downtown Core) - KEY DEMO CASCADE ROOT
    # Shared Upstream Dependency: SUB-001 powers water, telecom, 911 dispatch, highway
    # ---------------------------------------------------------
    RelationshipData(
        source_id="SUB-001",
        target_id="PUMP-001",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.98,
        estimated_restoration_hours=4.0,
        is_redundant=False,
        description="Feeds high-volume pumps at Downtown Water Pumping Station #1"
    ),
    RelationshipData(
        source_id="SUB-001",
        target_id="PUMP-002",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.92,
        estimated_restoration_hours=3.0,
        is_redundant=False,
        description="Feeds Financial District Booster Pump"
    ),
    RelationshipData(
        source_id="SUB-001",
        target_id="TOWER-001",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.95,
        estimated_restoration_hours=3.5,
        is_redundant=False,
        description="Primary power to Downtown Telecom Spine Mast"
    ),
    RelationshipData(
        source_id="SUB-001",
        target_id="EMERG-001",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.99,
        estimated_restoration_hours=3.0,
        is_redundant=False,
        description="Grid power to 911 Dispatch & EOC"
    ),
    RelationshipData(
        source_id="SUB-001",
        target_id="ROAD-001",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="traffic_control_power",
        confidence=0.90,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Powers intelligent traffic signals and illuminated signage on Grand Central Expressway"
    ),
    RelationshipData(
        source_id="SUB-001",
        target_id="CLINIC-001",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.91,
        estimated_restoration_hours=2.5,
        is_redundant=False,
        description="Primary feed to Downtown Urgent Care Center"
    ),

    # ---------------------------------------------------------
    # Power feeds from SUB-002 (North River)
    # Includes GENUINE ALTERNATE SUPPLY ROUTE: Auxiliary tie-line to TOWER-001
    # ---------------------------------------------------------
    RelationshipData(
        source_id="SUB-002",
        target_id="PUMP-003",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.95,
        estimated_restoration_hours=3.0,
        is_redundant=False,
        description="Powers North Reservoir Lift Station"
    ),
    RelationshipData(
        source_id="SUB-002",
        target_id="PUMP-004",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.90,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Powers Highland Hills Pressure Station"
    ),
    RelationshipData(
        source_id="SUB-002",
        target_id="TOWER-002",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.95,
        estimated_restoration_hours=2.5,
        is_redundant=False,
        description="Powers North Heights Cellular Mast"
    ),
    RelationshipData(
        source_id="SUB-002",
        target_id="TOWER-003",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.88,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Powers North River Hilltop Relay"
    ),
    RelationshipData(
        source_id="SUB-002",
        target_id="HOSP-002",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.98,
        estimated_restoration_hours=4.0,
        is_redundant=False,
        description="Primary power feed to North Memorial Specialty Hospital"
    ),
    RelationshipData(
        source_id="SUB-002",
        target_id="EMERG-002",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.94,
        estimated_restoration_hours=2.5,
        is_redundant=False,
        description="Primary power to North River Fire & Rescue HQ"
    ),
    RelationshipData(
        source_id="SUB-002",
        target_id="ROAD-003",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="traffic_control_power",
        confidence=0.89,
        estimated_restoration_hours=1.5,
        is_redundant=False,
        description="Powers North River Parkway signals"
    ),
    RelationshipData(
        source_id="SUB-002",
        target_id="CLINIC-002",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.90,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Powers Northside Pediatric & Family Clinic"
    ),
    # GENUINE ALTERNATE SUPPLY ROUTE: SUB-002 auxiliary tie-line to TOWER-001
    RelationshipData(
        source_id="SUB-002",
        target_id="TOWER-001",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="auxiliary_tie_line",
        confidence=0.88,
        estimated_restoration_hours=1.0,
        is_redundant=True,
        description="Auxiliary high-voltage tie-line that can restore power to TOWER-001 if SUB-001 trips"
    ),

    # ---------------------------------------------------------
    # Power feeds from SUB-003 (Eastside)
    # ---------------------------------------------------------
    RelationshipData(
        source_id="SUB-003",
        target_id="PUMP-005",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.92,
        estimated_restoration_hours=3.0,
        is_redundant=False,
        description="Powers Eastside Booster Pump #1"
    ),
    RelationshipData(
        source_id="SUB-003",
        target_id="PUMP-006",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.89,
        estimated_restoration_hours=2.5,
        is_redundant=False,
        description="Powers Eastside Secondary Distribution Pump"
    ),
    RelationshipData(
        source_id="SUB-003",
        target_id="TOWER-004",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.90,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Powers Eastside Relay Tower"
    ),
    RelationshipData(
        source_id="SUB-003",
        target_id="CLINIC-003",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.88,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Powers Eastside Community Health Clinic (vaccine refrigeration)"
    ),
    RelationshipData(
        source_id="SUB-003",
        target_id="CLINIC-004",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.90,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Powers Eastside Dialysis Center"
    ),
    RelationshipData(
        source_id="SUB-003",
        target_id="EMERG-003",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.91,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Powers Eastside EMS Station 4"
    ),
    RelationshipData(
        source_id="SUB-003",
        target_id="ROAD-005",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="traffic_control_power",
        confidence=0.87,
        estimated_restoration_hours=1.5,
        is_redundant=False,
        description="Powers Eastside Avenue traffic lighting and signals"
    ),

    # ---------------------------------------------------------
    # Power feeds from SUB-004 (Harbor)
    # ---------------------------------------------------------
    RelationshipData(
        source_id="SUB-004",
        target_id="PUMP-007",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.93,
        estimated_restoration_hours=3.5,
        is_redundant=False,
        description="Powers Harbor Marine Cooling & Fire Pump"
    ),
    RelationshipData(
        source_id="SUB-004",
        target_id="PUMP-008",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.89,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Powers Port Water Storage Lift Pump"
    ),
    RelationshipData(
        source_id="SUB-004",
        target_id="TOWER-005",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.94,
        estimated_restoration_hours=2.5,
        is_redundant=False,
        description="Powers Harbor Logistics Telemetry Tower"
    ),
    RelationshipData(
        source_id="SUB-004",
        target_id="CLINIC-005",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.86,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Powers Harbor Maritime Workers Clinic"
    ),
    RelationshipData(
        source_id="SUB-004",
        target_id="EMERG-004",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.96,
        estimated_restoration_hours=3.0,
        is_redundant=False,
        description="Powers Harbor Coast Guard & Port Rescue Station"
    ),
    RelationshipData(
        source_id="SUB-004",
        target_id="ROAD-006",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="traffic_control_power",
        confidence=0.88,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Powers Port Freight Highway automated weighing and signals"
    ),

    # ---------------------------------------------------------
    # Power feeds from SUB-005 & SUB-006 (West Industrial)
    # ---------------------------------------------------------
    RelationshipData(
        source_id="SUB-005",
        target_id="PUMP-009",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.99,
        estimated_restoration_hours=5.0,
        is_redundant=False,
        description="Powers Regional Central Water Treatment Plant (major municipal load)"
    ),
    RelationshipData(
        source_id="SUB-005",
        target_id="PUMP-010",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.92,
        estimated_restoration_hours=3.0,
        is_redundant=False,
        description="Powers West Chemical Scrubbing Water Pump"
    ),
    RelationshipData(
        source_id="SUB-005",
        target_id="TOWER-006",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.91,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Powers West Ridge Industrial Communications Mast"
    ),
    RelationshipData(
        source_id="SUB-005",
        target_id="CLINIC-006",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.88,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Powers West Industrial Occupational Health Facility"
    ),
    RelationshipData(
        source_id="SUB-005",
        target_id="EMERG-005",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="primary_feed",
        confidence=0.95,
        estimated_restoration_hours=3.0,
        is_redundant=False,
        description="Powers West Industrial Hazardous Materials Unit"
    ),
    RelationshipData(
        source_id="SUB-005",
        target_id="ROAD-008",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="traffic_control_power",
        confidence=0.87,
        estimated_restoration_hours=1.5,
        is_redundant=False,
        description="Powers West Industrial Beltway signaling"
    ),
    RelationshipData(
        source_id="SUB-006",
        target_id="ROAD-009",
        rel_type=RelationshipType.SUPPLIES_POWER_TO,
        dependency_type="rail_crossing_power",
        confidence=0.85,
        estimated_restoration_hours=1.5,
        is_redundant=False,
        description="Powers rail crossing gate and switchgear"
    ),

    # ---------------------------------------------------------
    # Water Supplies (Crucial for Chillers, Dialysis & Firefighting)
    # Multi-hop path: SUB-001 -> PUMP-001 -> HOSP-001 (water cooling failure cascade)
    # ---------------------------------------------------------
    RelationshipData(
        source_id="PUMP-009",
        target_id="PUMP-001",
        rel_type=RelationshipType.SUPPLIES_WATER_TO,
        dependency_type="bulk_treated_water_feed",
        confidence=0.97,
        estimated_restoration_hours=4.0,
        is_redundant=False,
        description="Central Treatment Plant sends bulk treated water to Downtown distribution"
    ),
    RelationshipData(
        source_id="PUMP-009",
        target_id="PUMP-007",
        rel_type=RelationshipType.SUPPLIES_WATER_TO,
        dependency_type="bulk_treated_water_feed",
        confidence=0.94,
        estimated_restoration_hours=4.0,
        is_redundant=False,
        description="Central Treatment Plant supplies Harbor industrial storage"
    ),
    RelationshipData(
        source_id="PUMP-009",
        target_id="PUMP-002",
        rel_type=RelationshipType.SUPPLIES_WATER_TO,
        dependency_type="auxiliary_bypass_pipeline",
        confidence=0.86,
        estimated_restoration_hours=2.0,
        is_redundant=True,
        description="Auxiliary bypass pipeline providing alternate supply to southern Downtown"
    ),
    RelationshipData(
        source_id="PUMP-001",
        target_id="HOSP-001",
        rel_type=RelationshipType.SUPPLIES_WATER_TO,
        dependency_type="chiller_and_potable",
        confidence=0.96,
        estimated_restoration_hours=4.5,
        is_redundant=False,
        description="Supplies high-pressure water for St. Jude chillers and surgical sterilization"
    ),
    RelationshipData(
        source_id="PUMP-001",
        target_id="CLINIC-001",
        rel_type=RelationshipType.SUPPLIES_WATER_TO,
        dependency_type="potable_and_sanitation",
        confidence=0.90,
        estimated_restoration_hours=3.0,
        is_redundant=False,
        description="Downtown Urgent Care potable water"
    ),
    RelationshipData(
        source_id="PUMP-003",
        target_id="HOSP-002",
        rel_type=RelationshipType.SUPPLIES_WATER_TO,
        dependency_type="potable_and_fire",
        confidence=0.95,
        estimated_restoration_hours=3.5,
        is_redundant=False,
        description="Potable water and fire suppression supply to North Memorial Hospital"
    ),
    RelationshipData(
        source_id="PUMP-005",
        target_id="CLINIC-003",
        rel_type=RelationshipType.SUPPLIES_WATER_TO,
        dependency_type="potable_water",
        confidence=0.88,
        estimated_restoration_hours=2.5,
        is_redundant=False,
        description="Eastside Clinic potable supply"
    ),
    RelationshipData(
        source_id="PUMP-005",
        target_id="CLINIC-004",
        rel_type=RelationshipType.SUPPLIES_WATER_TO,
        dependency_type="reverse_osmosis_dialysis_feed",
        confidence=0.96,
        estimated_restoration_hours=3.0,
        is_redundant=False,
        description="Essential water supply for Eastside Dialysis Center filtration"
    ),
    RelationshipData(
        source_id="PUMP-007",
        target_id="EMERG-004",
        rel_type=RelationshipType.SUPPLIES_WATER_TO,
        dependency_type="port_fire_suppression_main",
        confidence=0.94,
        estimated_restoration_hours=3.0,
        is_redundant=False,
        description="High-capacity fire hydrants for Harbor Coast Guard"
    ),
    RelationshipData(
        source_id="PUMP-007",
        target_id="CLINIC-005",
        rel_type=RelationshipType.SUPPLIES_WATER_TO,
        dependency_type="potable_water",
        confidence=0.85,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Harbor Clinic potable supply"
    ),

    # ---------------------------------------------------------
    # Communication Supports (911 Dispatch, Telemetry, SCADA)
    # Multi-hop path: SUB-001 -> TOWER-001 -> HOSP-001 (telemetry failure cascade)
    # Multi-hop path: SUB-001 -> TOWER-001 -> EMERG-001 (911 dispatch blackout)
    # ---------------------------------------------------------
    RelationshipData(
        source_id="TOWER-001",
        target_id="HOSP-001",
        rel_type=RelationshipType.SUPPORTS_COMMUNICATION_FOR,
        dependency_type="ambulance_telemetry_and_scada",
        confidence=0.97,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Provides critical telemetry feed from inbound ambulances to St. Jude Trauma Center"
    ),
    RelationshipData(
        source_id="TOWER-001",
        target_id="EMERG-001",
        rel_type=RelationshipType.SUPPORTS_COMMUNICATION_FOR,
        dependency_type="firstnet_emergency_radio",
        confidence=0.99,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Transmits 911 radio channels and CAD dispatch alerts across Downtown"
    ),
    RelationshipData(
        source_id="TOWER-001",
        target_id="ROAD-001",
        rel_type=RelationshipType.SUPPORTS_COMMUNICATION_FOR,
        dependency_type="traffic_sensor_telemetry",
        confidence=0.91,
        estimated_restoration_hours=1.5,
        is_redundant=False,
        description="Receives traffic congestion telemetry from Grand Central Expressway sensors"
    ),
    RelationshipData(
        source_id="TOWER-002",
        target_id="HOSP-002",
        rel_type=RelationshipType.SUPPORTS_COMMUNICATION_FOR,
        dependency_type="pediatric_telemetry",
        confidence=0.95,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Inbound patient telemetry for North Memorial"
    ),
    RelationshipData(
        source_id="TOWER-002",
        target_id="EMERG-002",
        rel_type=RelationshipType.SUPPORTS_COMMUNICATION_FOR,
        dependency_type="fire_rescue_dispatch",
        confidence=0.94,
        estimated_restoration_hours=1.5,
        is_redundant=False,
        description="Radio dispatch for North River Fire & Rescue"
    ),
    RelationshipData(
        source_id="TOWER-004",
        target_id="CLINIC-003",
        rel_type=RelationshipType.SUPPORTS_COMMUNICATION_FOR,
        dependency_type="telehealth_and_ehr_sync",
        confidence=0.88,
        estimated_restoration_hours=1.5,
        is_redundant=False,
        description="Cloud EHR sync and emergency backup communication"
    ),
    RelationshipData(
        source_id="TOWER-004",
        target_id="EMERG-003",
        rel_type=RelationshipType.SUPPORTS_COMMUNICATION_FOR,
        dependency_type="ems_radio_dispatch",
        confidence=0.92,
        estimated_restoration_hours=1.5,
        is_redundant=False,
        description="Dispatches ambulances for Eastside EMS Station 4"
    ),
    RelationshipData(
        source_id="TOWER-005",
        target_id="EMERG-004",
        rel_type=RelationshipType.SUPPORTS_COMMUNICATION_FOR,
        dependency_type="marine_vhf_ais_telemetry",
        confidence=0.96,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Maritime VHF distress channel and AIS transponder feeds"
    ),
    RelationshipData(
        source_id="TOWER-006",
        target_id="EMERG-005",
        rel_type=RelationshipType.SUPPORTS_COMMUNICATION_FOR,
        dependency_type="hazmat_sensor_telemetry",
        confidence=0.93,
        estimated_restoration_hours=1.5,
        is_redundant=False,
        description="Toxic gas plume and air monitoring sensor relay"
    ),

    # ---------------------------------------------------------
    # Road Access & Evacuation Connections
    # Includes GENUINE ALTERNATE ACCESS ROUTE: ROAD-002 to HOSP-001
    # ---------------------------------------------------------
    RelationshipData(
        source_id="ROAD-001",
        target_id="HOSP-001",
        rel_type=RelationshipType.CONNECTS_TO,
        dependency_type="primary_ambulance_arterial",
        confidence=0.92,
        estimated_restoration_hours=1.0,
        is_redundant=False,
        description="Expressway off-ramp leads directly into St. Jude Emergency Bay"
    ),
    # GENUINE ALTERNATE ACCESS ROUTE:
    RelationshipData(
        source_id="ROAD-002",
        target_id="HOSP-001",
        rel_type=RelationshipType.CONNECTS_TO,
        dependency_type="alternate_emergency_corridor",
        confidence=0.85,
        estimated_restoration_hours=1.0,
        is_redundant=True,
        description="Riverfront Boulevard provides alternate ambulance routing if Grand Central Expressway is jammed"
    ),
    RelationshipData(
        source_id="ROAD-003",
        target_id="HOSP-002",
        rel_type=RelationshipType.CONNECTS_TO,
        dependency_type="emergency_corridor",
        confidence=0.90,
        estimated_restoration_hours=1.0,
        is_redundant=False,
        description="Parkway connector to North Memorial Hospital"
    ),
    RelationshipData(
        source_id="ROAD-004",
        target_id="EMERG-002",
        rel_type=RelationshipType.CONNECTS_TO,
        dependency_type="fire_station_turnout",
        confidence=0.88,
        estimated_restoration_hours=0.5,
        is_redundant=False,
        description="Direct turnout for North River fire engines"
    ),
    RelationshipData(
        source_id="ROAD-005",
        target_id="CLINIC-003",
        rel_type=RelationshipType.CONNECTS_TO,
        dependency_type="community_arterial_access",
        confidence=0.87,
        estimated_restoration_hours=0.5,
        is_redundant=False,
        description="Patient and ambulance access to Eastside Clinic"
    ),
    RelationshipData(
        source_id="ROAD-006",
        target_id="EMERG-004",
        rel_type=RelationshipType.CONNECTS_TO,
        dependency_type="port_emergency_corridor",
        confidence=0.89,
        estimated_restoration_hours=1.0,
        is_redundant=False,
        description="Heavy response route to Coast Guard dock"
    ),
    RelationshipData(
        source_id="ROAD-008",
        target_id="EMERG-005",
        rel_type=RelationshipType.CONNECTS_TO,
        dependency_type="hazmat_evacuation_corridor",
        confidence=0.91,
        estimated_restoration_hours=1.0,
        is_redundant=False,
        description="Dedicated HazMat quick deployment route"
    ),

    # ---------------------------------------------------------
    # Backup Systems (HAS_BACKUP)
    # Includes:
    # 1. Operational Backup: HOSP-001 -> GEN-001
    # 2. INSUFFICIENT Backup: PUMP-001 -> GEN-002 (1.2 MW vs 3.0 MW required)
    # 3. UNAVAILABLE Backup: CLINIC-003 -> GEN-005 (status FAILED / seized)
    # ---------------------------------------------------------
    RelationshipData(
        source_id="HOSP-001",
        target_id="GEN-001",
        rel_type=RelationshipType.HAS_BACKUP,
        dependency_type="onsite_emergency_generator",
        confidence=0.99,
        estimated_restoration_hours=0.2,
        is_redundant=True,
        description="St. Jude maintains automatic transfer switch with GEN-001 (12h diesel capacity)"
    ),
    # INSUFFICIENT CAPACITY BACKUP:
    RelationshipData(
        source_id="PUMP-001",
        target_id="GEN-002",
        rel_type=RelationshipType.HAS_BACKUP,
        dependency_type="deployable_mobile_generator",
        confidence=0.75,
        estimated_restoration_hours=2.0,
        is_redundant=True,
        description="GEN-002 deployable to PUMP-001, but capacity (1.2MW) is INSUFFICIENT for 3.0MW full station load"
    ),
    RelationshipData(
        source_id="HOSP-002",
        target_id="GEN-003",
        rel_type=RelationshipType.HAS_BACKUP,
        dependency_type="onsite_emergency_generator",
        confidence=0.98,
        estimated_restoration_hours=0.2,
        is_redundant=True,
        description="North Memorial automatic backup generator"
    ),
    RelationshipData(
        source_id="EMERG-002",
        target_id="GEN-004",
        rel_type=RelationshipType.HAS_BACKUP,
        dependency_type="station_standby_generator",
        confidence=0.95,
        estimated_restoration_hours=0.1,
        is_redundant=True,
        description="North River Fire HQ station emergency generator"
    ),
    # UNAVAILABLE / FAILED BACKUP:
    RelationshipData(
        source_id="CLINIC-003",
        target_id="GEN-005",
        rel_type=RelationshipType.HAS_BACKUP,
        dependency_type="onsite_emergency_generator",
        confidence=0.0,
        estimated_restoration_hours=24.0,
        is_redundant=True,
        description="UNAVAILABLE BACKUP: GEN-005 starter motor is seized; cannot auto-start or supply power"
    ),
    RelationshipData(
        source_id="EMERG-004",
        target_id="GEN-006",
        rel_type=RelationshipType.HAS_BACKUP,
        dependency_type="maritime_standby_generator",
        confidence=0.96,
        estimated_restoration_hours=0.2,
        is_redundant=True,
        description="Coast Guard marine diesel standby generator"
    ),
    RelationshipData(
        source_id="PUMP-009",
        target_id="GEN-007",
        rel_type=RelationshipType.HAS_BACKUP,
        dependency_type="utility_scale_gas_turbine",
        confidence=0.99,
        estimated_restoration_hours=0.5,
        is_redundant=True,
        description="Regional Central Water Treatment Plant dual-fuel turbine backup"
    ),

    # ---------------------------------------------------------
    # General DEPENDS_ON Semantic Relationships
    # ---------------------------------------------------------
    RelationshipData(
        source_id="HOSP-001",
        target_id="PUMP-001",
        rel_type=RelationshipType.DEPENDS_ON,
        dependency_type="cooling_water_dependency",
        confidence=0.95,
        estimated_restoration_hours=4.0,
        is_redundant=False,
        description="Hospital HVAC requires chilled water loop from PUMP-001"
    ),
    RelationshipData(
        source_id="HOSP-001",
        target_id="TOWER-001",
        rel_type=RelationshipType.DEPENDS_ON,
        dependency_type="ambulance_telemetry_dependency",
        confidence=0.97,
        estimated_restoration_hours=2.0,
        is_redundant=False,
        description="Trauma Center requires live telemetry to prepare surgical teams for inbound patients"
    ),
    RelationshipData(
        source_id="EMERG-001",
        target_id="TOWER-001",
        rel_type=RelationshipType.DEPENDS_ON,
        dependency_type="telecom_spine_dependency",
        confidence=0.99,
        estimated_restoration_hours=3.0,
        is_redundant=False,
        description="Dispatch center cannot broadcast CAD alerts to first responders without TOWER-001"
    ),
    RelationshipData(
        source_id="CLINIC-004",
        target_id="PUMP-005",
        rel_type=RelationshipType.DEPENDS_ON,
        dependency_type="dialysis_water_dependency",
        confidence=0.96,
        estimated_restoration_hours=3.0,
        is_redundant=False,
        description="Dialysis filtration stations cannot operate without continuous water pressure"
    ),
]


def seed_database(client: Optional[FalkorDBClient] = None, clear_existing: bool = False) -> dict[str, int]:
    """Populates FalkorDB with the synthetic Ripple City infrastructure graph.
    
    Uses Cypher MERGE commands for 100% idempotent insertion.
    Safely updates existing nodes with domain labels without deleting the graph.
    
    Returns counts of seeded nodes and relationships.
    """
    db = client or db_client
    if clear_existing:
        logger.info(f"Clearing existing graph {db.graph_name} before seeding...")
        db.delete_graph()

    # 1. Ensure indexes exist for high-speed queries on InfrastructureNode and domain labels
    index_labels = [
        "InfrastructureNode", "Substation", "WaterPump", "MobileTower",
        "Hospital", "Clinic", "EmergencyCenter", "Road", "BackupGenerator",
        "InfrastructureZone", "Incident", "RecoveryAction", "EvidenceRecord"
    ]
    for lbl in index_labels:
        try:
            db.query(f"CREATE INDEX FOR (n:{lbl}) ON (n.id)")
        except Exception as e:
            logger.debug(f"Index creation note for {lbl}: {e}")

    # 2. Seed Infrastructure Zones
    zones_seeded = 0
    zone_cypher = """
    MERGE (z:InfrastructureNode {id: $id})
    SET z:InfrastructureZone,
        z.name = $name,
        z.entity_type = $entity_type,
        z.criticality = $criticality,
        z.status = $status,
        z.zone = $zone,
        z.latitude = $latitude,
        z.longitude = $longitude,
        z.buffer_hours = $buffer_hours,
        z.capacity_rating = $capacity_rating,
        z.notes = $notes
    RETURN z.id
    """
    for zone in SYNTHETIC_ZONES:
        db.query(zone_cypher, {
            "id": zone.id,
            "name": zone.name,
            "entity_type": zone.entity_type.value,
            "criticality": zone.criticality.value,
            "status": zone.status.value,
            "zone": zone.zone,
            "latitude": zone.latitude,
            "longitude": zone.longitude,
            "buffer_hours": zone.buffer_hours,
            "capacity_rating": zone.capacity_rating or "",
            "notes": zone.notes or "",
        })
        zones_seeded += 1

    # 3. Seed Infrastructure Nodes (with domain label SET n:{entity_type})
    nodes_seeded = 0
    for node in SYNTHETIC_NODES:
        node_cypher = f"""
        MERGE (n:InfrastructureNode {{id: $id}})
        SET n:{node.entity_type.value},
            n.name = $name,
            n.entity_type = $entity_type,
            n.criticality = $criticality,
            n.status = $status,
            n.zone = $zone,
            n.latitude = $latitude,
            n.longitude = $longitude,
            n.buffer_hours = $buffer_hours,
            n.capacity_rating = $capacity_rating,
            n.notes = $notes
        RETURN n.id
        """
        db.query(node_cypher, {
            "id": node.id,
            "name": node.name,
            "entity_type": node.entity_type.value,
            "criticality": node.criticality.value,
            "status": node.status.value,
            "zone": node.zone,
            "latitude": node.latitude,
            "longitude": node.longitude,
            "buffer_hours": node.buffer_hours,
            "capacity_rating": node.capacity_rating or "",
            "notes": node.notes or "",
        })
        nodes_seeded += 1

    # 4. Link Infrastructure Nodes to their respective InfrastructureZone via LOCATED_IN
    zone_mapping = {
        "Downtown": "ZONE-DTN",
        "North River": "ZONE-NR",
        "Eastside": "ZONE-EST",
        "Harbor": "ZONE-HBR",
        "West Industrial": "ZONE-WST",
    }
    zone_links_created = 0
    for node in SYNTHETIC_NODES:
        zone_id = zone_mapping.get(node.zone)
        if zone_id:
            loc_cypher = """
            MATCH (n:InfrastructureNode {id: $node_id}), (z:InfrastructureZone {id: $zone_id})
            MERGE (n)-[r:LOCATED_IN]->(z)
            RETURN type(r)
            """
            db.query(loc_cypher, {"node_id": node.id, "zone_id": zone_id})
            zone_links_created += 1

    # 5. Seed Infrastructure Dependency Relationships
    relationships_seeded = 0
    for rel in SYNTHETIC_RELATIONSHIPS:
        rel_cypher = f"""
        MATCH (src:InfrastructureNode {{id: $source_id}}), (dst:InfrastructureNode {{id: $target_id}})
        MERGE (src)-[r:{rel.rel_type.value}]->(dst)
        SET r.dependency_type = $dependency_type,
            r.confidence = $confidence,
            r.estimated_restoration_hours = $estimated_restoration_hours,
            r.is_redundant = $is_redundant,
            r.description = $description
        RETURN type(r)
        """
        db.query(rel_cypher, {
            "source_id": rel.source_id,
            "target_id": rel.target_id,
            "dependency_type": rel.dependency_type,
            "confidence": rel.confidence,
            "estimated_restoration_hours": rel.estimated_restoration_hours,
            "is_redundant": rel.is_redundant,
            "description": rel.description or "",
        })
        relationships_seeded += 1

    # 6. Seed Baseline Historical Incident Record (Incident, RecoveryAction, EvidenceRecord)
    # Provides verified ground truth for agent incident memory retrieval
    try:
        db.query("""
        MERGE (inc:Incident {id: 'INC-2026-001'})
        SET inc.title = 'Simulated Phase Imbalance & Downtown Grid Trip',
            inc.failure_source = 'SUB-001',
            inc.timestamp = '2026-10-14T08:30:00Z',
            inc.root_cause_type = 'Phase Imbalance / Transformer Overheat',
            inc.severity = 'CRITICAL',
            inc.simulated = true,
            inc.resolved = true,
            inc.notes = 'Historic baseline simulation. Demonstrates auxiliary tie-line recovery.'
        """)
        db.query("MATCH (inc:Incident {id: 'INC-2026-001'}), (sub:Substation {id: 'SUB-001'}) MERGE (inc)-[:TRIGGERED_BY]->(sub)")
        db.query("MATCH (inc:Incident {id: 'INC-2026-001'}), (h:Hospital {id: 'HOSP-001'}) MERGE (inc)-[:AFFECTED]->(h)")
        db.query("MATCH (inc:Incident {id: 'INC-2026-001'}), (t:MobileTower {id: 'TOWER-001'}) MERGE (inc)-[:AFFECTED]->(t)")
        db.query("""
        MATCH (inc:Incident {id: 'INC-2026-001'})
        MERGE (act:RecoveryAction {id: 'ACT-2026-001'})
        SET act.action_name = 'Auxiliary Grid Re-route from SUB-002',
            act.action_type = 'REROUTE_SUPPLY',
            act.target_node_id = 'TOWER-001',
            act.estimated_hours = 1.0,
            act.expected_benefit = 'Restored telecom spine & 911 dispatch without waiting for SUB-001 repairs',
            act.status = 'EXECUTED_SUCCESSFUL'
        MERGE (inc)-[:USED_ACTION]->(act)
        """)
        db.query("MATCH (act:RecoveryAction {id: 'ACT-2026-001'}), (tow:MobileTower {id: 'TOWER-001'}) MERGE (act)-[:TARGETS]->(tow)")
        db.query("""
        MATCH (inc:Incident {id: 'INC-2026-001'})
        MERGE (evd:EvidenceRecord {id: 'EVD-2026-001'})
        SET evd.source_id = 'SUB-001',
            evd.target_id = 'HOSP-001',
            evd.path_hops = 2,
            evd.path_summary = 'SUB-001 -> PUMP-001 -> HOSP-001 (Chiller Water Deprivation)',
            evd.confidence = 0.98
        MERGE (inc)-[:SUPPORTED_BY]->(evd)
        """)
        logger.info("Baseline incident memory record seeded successfully.")
    except Exception as e:
        logger.warning(f"Baseline incident seeding note: {e}")

    total_infra_nodes = zones_seeded + nodes_seeded
    total_relationships = relationships_seeded + zone_links_created
    logger.info(
        f"Seeding completed successfully: {total_infra_nodes} infrastructure nodes, "
        f"{total_relationships} relationships (including {zone_links_created} zone links)."
    )

    return {
        "nodes": total_infra_nodes,
        "relationships": total_relationships,
        "infrastructure_nodes": nodes_seeded,
        "zones": zones_seeded,
        "dependency_relationships": relationships_seeded,
        "zone_links": zone_links_created,
    }


if __name__ == "__main__":
    print("Initiating Ripple City synthetic infrastructure graph seeding...")
    stats = seed_database(clear_existing=False)
    print(f"Seeding success! Total Infrastructure Nodes: {stats['nodes']}, Total Relationships: {stats['relationships']}")
