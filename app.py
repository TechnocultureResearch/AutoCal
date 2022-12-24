import streamlit as st
from dataclasses import dataclass
from typing import Optional, Self, Dict, Tuple, NamedTuple
import ezdxf as ez
from io import BytesIO, StringIO
import re
import math
import geojson


@dataclass
class LongLat:
    longitude: float
    latitude: float

    @classmethod
    def from_string(cls, string) -> Optional[Self]:
        '''
        regex to convert a string in the format "N 4792384, E 798797" to a LongLat object
        '''
        print(string)
        pattern = r'([NS])\s*(\d+\.\d+),\s*([EW])\s*(\d+\.\d+)'
        match = re.search(pattern, string)
        # print(match)

        if match is None:
            return None
        return cls(longitude=float(match.group(2)), latitude=float(match.group(4)))


@dataclass
class CalPoint:
    '''Calliberation Point: a geographical point with a name'''
    name: str
    longlat: LongLat


@dataclass
class DxfGeometry:
    point_a: CalPoint
    point_b: CalPoint
    point_c: CalPoint
    boundary: ez.entities.Polyline


class Transform(NamedTuple):
    s: float
    dx: float
    dy: float
    theta: float


def file_found(entity):
    st.success(
        f"Found in file: Entity={entity}, Layer={entity.dxf.layer}")


def process_dxf_file(dxf_file: ez.document.Drawing) -> DxfGeometry:
    dxf_cal_points = {}
    dxf_boundary = None

    for entity in dxf_file.modelspace():
        match entity.dxftype():
            case 'POLYLINE':
                if entity.dxf.layer == "POLYLINE":
                    dxf_boundary = entity
                    file_found(entity)
            case 'POINT':
                if entity.dxf.layer in ["POINT_A", "POINT_B", "POINT_C"]:
                    dxf_cal_points[entity.dxf.layer] = CalPoint(
                        name=entity.dxf.layer, longlat=LongLat(longitude=entity.dxf.location[0], latitude=entity.dxf.location[1]))
                    file_found(entity)

    return DxfGeometry(
        dxf_cal_points["POINT_A"], dxf_cal_points["POINT_B"], dxf_cal_points["POINT_C"], dxf_boundary)


def calculate_transform_params(cal_points: Dict[str, CalPoint], dxf_geometry: DxfGeometry) -> Transform:
    dx = cal_points["A"].longitude - dxf_geometry.point_a.longlat.longitude
    dy = cal_points["A"].latitude - dxf_geometry.point_a.longlat.latitude

    dxa = cal_points["B"].longitude - cal_points["A"].longitude
    dya = cal_points["B"].latitude - cal_points["A"].latitude
    dxb = dxf_geometry.point_b.longlat.longitude - \
        dxf_geometry.point_a.longlat.longitude
    dyb = dxf_geometry.point_b.longlat.latitude - \
        dxf_geometry.point_a.longlat.latitude

    s = (dxa * dxb + dya * dyb) / (dxb**2 + dyb**2)
    theta = math.atan2(dya, dxa) - math.atan2(dyb, dxb)

    return Transform(s, dx, dy, theta)


def generate_calibrated_geojson(cal_points: Dict[str, LongLat], dxf_geometry: DxfGeometry) -> geojson.Feature:
    s, dx, dy, theta = calculate_transform_params(cal_points, dxf_geometry)

    def transform_point(point_dxf: CalPoint) -> Tuple[float, float]:
        x_dxf = point_dxf.longlat.longitude
        y_dxf = point_dxf.longlat.latitude
        x_real = s * x_dxf + dx
        y_real = s * y_dxf + dy
        print(
            f"Transformed point {point_dxf.name} from {x_dxf}, {y_dxf}: {x_real}, {y_real}")
        return x_real, y_real

    # transform calibration points
    point_a_real = transform_point(dxf_geometry.point_a)
    point_b_real = transform_point(dxf_geometry.point_b)
    point_c_real = transform_point(dxf_geometry.point_c)

    # transform boundary polygon
    boundary_vertices_real = []
    for vertex in dxf_geometry.boundary.vertices:
        print(vertex)
        x_dxf = vertex.dxf.location[0]
        y_dxf = vertex.dxf.location[1]
        x_real = s * x_dxf + dx
        y_real = s * y_dxf + dy
        boundary_vertices_real.append((x_real, y_real))

    # construct GeoJSON object
    geometry = geojson.Polygon([boundary_vertices_real])
    properties = {
        "point_a": {
            "name": dxf_geometry.point_a.name,
            "longitude": point_a_real[0],
            "latitude": point_a_real[1]
        },
        "point_b": {
            "name": dxf_geometry.point_b.name,
            "longitude": point_b_real[0],
            "latitude": point_b_real[1]
        },
        "point_c": {
            "name": dxf_geometry.point_c.name,
            "longitude": point_c_real[0],
            "latitude": point_c_real[1]
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
