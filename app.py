import streamlit as st
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, NamedTuple
import ezdxf as ez
from io import BytesIO, StringIO
import re
import math
import geojson


@dataclass
class LongLat:
    '''A class to represent a longitude and latitude pair.
    Example:
    >>> LongLat(0, 0)
    LongLat(longitude=0, latitude=0)
    >>> LongLat.from_string("N 32.742, E 23.23")
    LongLat(longitude=32.742, latitude=23.23)
    '''
    longitude: float
    latitude: float

    @classmethod
    def from_string(cls, string) -> Optional["Self"]:
        '''
        regex to convert a string in the format "N 47.2384, E 7.8797" to a LongLat object
        '''
        pattern = r'([NS])\s*(\d+\.\d+),\s*([EW])\s*(\d+\.\d+)'
        match = re.search(pattern, string)
        if match is None: return None
        return cls(longitude=float(match.group(2)), latitude=float(match.group(4)))

    def distance(self, other: "LongLat") -> float:
        '''
        Calculate the distance between two LongLat objects
        Example:
        >>> LongLat(0, 0).distance(LongLat(0, 1))
        1.0
        '''
        return math.sqrt((self.longitude - other.longitude)**2 + (self.latitude - other.latitude)**2)

    def __sub__(self, other: "LongLat") -> float:
        '''
        Calculate the distance between two LongLat objects
        Example:
        >>> LongLat(0, 0) - LongLat(0, 1)
        1.0
        '''
        return self.distance(other)


@dataclass
class CalPoint:
    '''Calliberation Point: a geographical point with a name
    Example:
    >>> CalPoint("A", LongLat(0, 0))
    CalPoint(name='A', longlat=LongLat(longitude=0, latitude=0))
    '''
    name: str
    longlat: LongLat


@dataclass
class DxfGeometry:
    '''
    A class to represent a DXF geometry object containing a list of 3 points and a polyline
    '''
    point_a: CalPoint
    point_b: CalPoint
    point_c: CalPoint
    boundary: ez.entities.Polyline


class Transform(NamedTuple):
    '''
    A class to represent a transformation matrix
    Example:
    >>> Transform(1, 2, 2, 1)
    Transform(s=1, dx=2, dy=2, theta=1)
    '''
    s: float
    dx: float
    dy: float
    theta: float


def file_found(entity: ez.entities.DXFEntity):
    st.success(
        f"Found in file: Entity={entity}, Layer={entity.dxf.layer}")


def process_dxf_file(dxf_file: ez.document.Drawing) -> DxfGeometry:
    dxf_cal_points = {}
    dxf_boundary = None

    for entity in dxf_file.modelspace():
        if entity.dxftype() == 'POLYLINE':
            if entity.dxf.layer == "POLYLINE":
                dxf_boundary = entity
                file_found(entity)
        elif entity.dxftype() == 'POINT':
            if entity.dxf.layer in ["POINT_A", "POINT_B", "POINT_C"]:
                dxf_cal_points[entity.dxf.layer] = CalPoint(
                    name=entity.dxf.layer, longlat=LongLat(longitude=entity.dxf.location[0], latitude=entity.dxf.location[1]))
                file_found(entity)

    return DxfGeometry(
        dxf_cal_points["POINT_A"], dxf_cal_points["POINT_B"], dxf_cal_points["POINT_C"], dxf_boundary)


class PointTriplet(NamedTuple):
    '''
    A class to represent a triplet of points
    '''
    A: CalPoint
    B: CalPoint
    C: CalPoint


def calculate_transform_params(cal_points: Dict[str, LongLat], cad_points: PointTriplet) -> Transform:
    '''
    Calculate the transformation parameters for a given set of calibration points and target points
    Example:
    >>> calculate_transform_params({"A": LongLat(0, 0), "B": LongLat(1, 0), "C": LongLat(0, 1)}, PointTriplet(CalPoint("A", LongLat(0, 0)), CalPoint("B", LongLat(1, 0)), CalPoint("C", LongLat(0, 1))))
    Transform(s=1.0, dx=0.0, dy=0.0, theta=0.0)
    >>> calculate_transform_params({"A": LongLat(0, 0), "B": LongLat(1, 0), "C": LongLat(0, 1)}, PointTriplet(CalPoint("A", LongLat(0, 0)), CalPoint("B", LongLat(2, 0)), CalPoint("C", LongLat(0, 2))))
    Transform(s=0.5, dx=0.0, dy=0.0, theta=0.0)
    >>> calculate_transform_params({"A": LongLat(0, 0), "B": LongLat(1, 0), "C": LongLat(0, 1)}, PointTriplet(CalPoint("A", LongLat(0, 0)), CalPoint("B", LongLat(0, 1)), CalPoint("C", LongLat(1, 0))))
    Transform(s=1.0, dx=0.0, dy=0.0, theta=1.5707963267948966)
    >>> calculate_transform_params({"A": LongLat(0, 0), "B": LongLat(1, 0), "C": LongLat(0, 1)}, PointTriplet(CalPoint("A", LongLat(1, 1)), CalPoint("B", LongLat(2, 1)), CalPoint("C", LongLat(1, 2))))
    Transform(s=1.0, dx=-1.0, dy=-1.0, theta=0.0)
    '''
    (A, B, _) = cad_points.A.longlat, cad_points.B.longlat, cad_points.C.longlat
    (a, b, _) = (cal_points["A"], cal_points["B"], cal_points["C"])

    # calculate the lateral shift
    dx = float(a.longitude - A.longitude)
    dy = float(a.latitude - A.latitude)

    # calculate the scale factor
    print(f"{a} - {b} = {a - b}")
    print(f"{A} - {B} = {A - B}")
    s = (a - b)/(A - B)
    print(f"s = {s}")

    # calculate the rotation angle
    theta = math.atan2(
        (B.latitude - A.latitude), (B.longitude - A.longitude)) - math.atan2(
        (b.latitude - a.latitude), (b.longitude - a.longitude))
    
    return Transform(s, dx, dy, theta)


def transform_point(point: LongLat, transform: Transform) -> Tuple[float, float]:
    '''
    Transform a point using the given transformation parameters
    Example:
    >>> transform_point(LongLat(0, 0), Transform(1, 0, 0, 0))
    (0.0, 0.0)
    >>> transform_point(LongLat(1, 0), Transform(2, 0, 0, 0))
    (2.0, 0.0)
    >>> a, b = transform_point(LongLat(0, 1), Transform(1, 0, 0, -1.5707963267948966)) 
    >>> A, B = (1.0, 0.0) 
    >>> a-A < 0.0001
    True
    >>> b-B < 0.0001
    True
    '''
    x, y = point.longitude, point.latitude
    s, dx, dy, theta = transform

    x = x * s + dx
    y = y * s + dy

    x, y = x * math.cos(theta) - y * math.sin(theta), x * math.sin(theta) + y * math.cos(theta)

    return (x, y)


def transform_cal_points(cad_points: PointTriplet, transform: Transform) -> Dict[str, LongLat]:
    '''
    Transform the CAD calliberation points using the given transformation parameters
    Example:
    >>> transform_cal_points(PointTriplet(CalPoint("A", LongLat(0, 0)), CalPoint("B", LongLat(1, 0)), CalPoint("C", LongLat(0, 1))), Transform(2, 2, 2, 0))
    {'A': LongLat(longitude=2.0, latitude=2.0), 'B': LongLat(longitude=4.0, latitude=2.0), 'C': LongLat(longitude=2.0, latitude=4.0)}
    '''
    # transform the CAD points
    point_a_real = transform_point(cad_points.A.longlat, transform)
    point_b_real = transform_point(cad_points.B.longlat, transform)
    point_c_real = transform_point(cad_points.C.longlat, transform)

    return {
        "A": LongLat(longitude=point_a_real[0], latitude=point_a_real[1]),
        "B": LongLat(longitude=point_b_real[0], latitude=point_b_real[1]),
        "C": LongLat(longitude=point_c_real[0], latitude=point_c_real[1])
    }


def generate_calibrated_geojson(cal_points: Dict[str, LongLat], dxf_geometry:DxfGeometry ) -> geojson.Feature:
    '''
    Generate a geojson feature from the given calibration points and DXF geometry
    '''
    transform = calculate_transform_params(cal_points, PointTriplet(dxf_geometry.point_a, dxf_geometry.point_b, dxf_geometry.point_c))
    cal_real = transform_cal_points(PointTriplet(dxf_geometry.point_a, dxf_geometry.point_b, dxf_geometry.point_c), transform)

    # transform boundary polygon
    boundary_vertices_real = []
    for vertex in dxf_geometry.boundary.vertices:
        x_real, y_real = transform_point(LongLat(vertex.dxf.location[0], vertex.dxf.location[1]), transform)
        boundary_vertices_real.append((x_real, y_real))

    print("| Transform | Real |")
    print("| --- | --- |")
    print("| {} | {} |".format(cal_real["A"], cal_points["A"]))
    print("| {} | {} |".format(cal_real["B"], cal_points["B"]))
    print("| {} | {} |".format(cal_real["C"], cal_points["C"]))

    # construct GeoJSON object
    geometry = geojson.Polygon([boundary_vertices_real])
    properties = {
        "point_a": {
            "name": dxf_geometry.point_a.name,
            "longitude": cal_real["A"].longitude,
            "latitude": cal_real["A"].latitude
        },
        " cal_real": {
            "name": dxf_geometry.point_b.name,
            "longitude": cal_real["B"].longitude,
            "latitude": cal_real["B"].latitude
        },
        "point_c": {
            "name": dxf_geometry.point_c.name,
            "longitude": cal_real["C"].longitude,
            "latitude": cal_real["C"].latitude
        }
    }

    feature = geojson.Feature(geometry=geometry, properties=properties)
    return feature


if __name__ == "__main__":
    st.image('https://www.vastuvihar.org/images/vastulogo.png', width=180)
    st.title("AutoCal")
    st.write("Convert Dwg Files to geoJSON")

    dxf_geometry: Optional[DxfGeometry] = None

    file = st.file_uploader("Upload Dxf File", type=["dxf"])
    dxf_file = None
    if file is not None:
        file_val = StringIO(file.getvalue().decode('utf-8'))
        try:
            dxf_file = ez.read(file_val)
        except ez.DXFStructureError as e:
            st.error("DXF file is not valid. {}".format(e))

        dxf_geometry = process_dxf_file(dxf_file)

    if dxf_file is not None:
        cal_points_str = {}
        cal_points_str["A"] = st.text_input(f"Cal Point A")
        cal_points_str["B"] = st.text_input(f"Cal Point B")
        cal_points_str["C"] = st.text_input(f"Cal Point C")

        cal_points = {}
        cal_points["A"] = LongLat.from_string(cal_points_str["A"])
        cal_points["B"] = LongLat.from_string(cal_points_str["B"])
        cal_points["C"] = LongLat.from_string(cal_points_str["C"])

        invalid_count = 0
        for key, value in cal_points.items():
            if value is None:
                invalid_count += 1
                st.error(f"Cal Point {key} is not valid")
                break

        if invalid_count == 0:
            if st.button("Generate GeoJSON"):
                print(cal_points)
                print(dxf_geometry)

                if dxf_geometry is not None:
                    calibrated_geojson = generate_calibrated_geojson(
                        cal_points, dxf_geometry)
                    st.write(calibrated_geojson)
