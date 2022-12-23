import streamlit as st
from dataclasses import dataclass
from typing import Optional, Self
import ezdxf as ez
from io import BytesIO, StringIO


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

        import re
        pattern = r'([NS])\s*(\d+\.\d+),\s*([EW])\s*(\d+\.\d+)'

        match = re.search(pattern, string)

        print(match)

        if match is None:
            return None

        return cls(longitude=float(match.group(2)), latitude=float(match.group(4)))


@dataclass
class CalPoint:
    name: str
    longlat: LongLat


if __name__ == "__main__":
    st.image('https://www.vastuvihar.org/images/vastulogo.png', width=180)
    st.title("AutoCal")
    st.write("Convert Dwg Files to geoJSON")

    file = st.file_uploader("Upload Dwg File", type=["dxf"])

    dxf_file = None
    if file is not None:
        file_val = StringIO(file.getvalue().decode('utf-8'))
        try:
            dxf_file = ez.read(file_val)
        except ez.DXFStructureError as e:
            st.error("DXF file is not valid. {}".format(e))

        # print(dwg)

    if dxf_file is not None:
        # cal_point_count = st.number_input("Number of Calliberation Points", min_value=3, max_value=10, value=3)
        cal_point_count = 3

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
            if st.button("Convert"):
                st.write(cal_points)
