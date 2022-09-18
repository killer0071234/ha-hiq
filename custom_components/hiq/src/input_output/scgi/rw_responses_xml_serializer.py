from xml.etree.cElementTree import Element
from xml.etree.cElementTree import SubElement
from xml.etree.cElementTree import tostring

from ...services.rw_service.scgi_communication.r_response import RResponse


class RWResponsesXmlSerializer:
    @classmethod
    def to_xml(cls, responses, reply_with_description):
        data = Element("data")

        if len(responses) == 0:
            response = RResponse(
                "", "?", "", "", False, RResponse.Code.DEVICE_NOT_FOUND, False
            )
            responses.append(response)

        for response in responses:

            var = SubElement(data, "var")
            SubElement(var, "name").text = response.name

            value_sub_element = SubElement(var, "value")

            if isinstance(response.value, list):
                for item in response.value:
                    SubElement(value_sub_element, "item").text = item
            else:
                value_sub_element.text = str(response.value) if response.valid else "?"

            if reply_with_description:
                SubElement(var, "description").text = response.description

            if response.code != RResponse.Code.NO_ERROR:
                SubElement(var, "error_code").text = str(response.code.value)

        content = tostring(data, encoding="unicode")

        return '<?xml version="1.0" encoding="ISO-8859-1"?>' + content
