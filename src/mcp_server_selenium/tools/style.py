"""
Style tools for Selenium MCP server.

This module provides tools for getting style information from web page elements.
"""

import json
import logging

from selenium.webdriver.common.by import By

# Import the global mcp instance from the main server module
from ..server import mcp, ensure_driver_initialized

logger = logging.getLogger(__name__)


@mcp.tool()
def get_style_an_element(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', in_iframe_id: str = '', in_iframe_name: str = '', return_html: bool = False, xpath: str = '', all_styles: bool = True, computed_style: bool = True) -> str:
    """Get style information for an element identified by text content, class name, or ID.
    
    This tool finds an element based on specified criteria and returns its style information. At least one 
    of text, class_name, id, attributes, element_type, or xpath must be provided. If multiple elements match the criteria, 
    or if no elements are found, an error message is returned.
    
    Args:
        text: Text content of the element to find. Case-sensitive text matching.
        class_name: CSS class name of the element to find.
        id: ID attribute of the element to find.
        attributes: Dictionary of attribute name-value pairs to match (e.g. {'data-test': 'button'}).
        element_type: HTML element type to find (e.g. 'div', 'input', 'h1', 'button', etc.).
        in_iframe_id: ID of the iframe to search within. If provided, the function will switch to this iframe before searching.
        in_iframe_name: Name of the iframe to search within. If provided and in_iframe_id is not provided, the function will switch to this iframe before searching.
        return_html: Return the HTML content of the element instead of JSON information.
        xpath: Direct XPath selector to find the element. When provided, other selection criteria are ignored.
        all_styles: When True, return actual styles the browser is applying (whether from inline, CSS file, or defaults) - equivalent to Styles tab in Chrome dev tools.
        computed_style: When True, return computed styles (what Computed tab shows in Chrome dev tool).
    
    Returns:
        A JSON string with style information about the found element or an error message.
        If return_html is True, returns the HTML content of the element.
    """
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    if text == '' and class_name == '' and id == '' and not attributes and element_type == '' and xpath == '':
        return "Error: At least one of text, class_name, id, attributes, element_type, or xpath must be provided"
    
    try:
        # Remember the original context to switch back later
        original_context = True
        
        # Switch to iframe if specified
        if in_iframe_id or in_iframe_name:
            logger.info(f"Switching to iframe with id='{in_iframe_id}' or name='{in_iframe_name}'")
            try:
                if in_iframe_id:
                    # First try to find the iframe by ID
                    iframe = driver.find_element(By.ID, in_iframe_id)
                    driver.switch_to.frame(iframe)
                    logger.info(f"Successfully switched to iframe with id='{in_iframe_id}'")
                elif in_iframe_name:
                    # If ID not provided, try by name
                    driver.switch_to.frame(in_iframe_name)
                    logger.info(f"Successfully switched to iframe with name='{in_iframe_name}'")
                original_context = False
            except Exception as iframe_e:
                error_msg = f"Error switching to iframe: {str(iframe_e)}"
                logger.error(error_msg)
                return error_msg
        
        # If xpath is provided, use it directly
        if xpath != '':
            logger.info(f"Looking for elements with provided XPath: {xpath}")
            elements = driver.find_elements(By.XPATH, xpath)
        else:
            # Build XPath conditions based on provided arguments
            conditions = []
            
            if id != '':
                conditions.append(f"@id='{id}'")
            
            if class_name != '':
                # Handle multiple class names by ensuring each is present
                for cn in class_name.split():
                    conditions.append(f"contains(@class, '{cn}')")
            
            if text != '':
                conditions.append(f"contains(text(), '{text}')")
                
            # Add conditions for additional attributes
            for attr_name, attr_value in attributes.items():
                conditions.append(f"@{attr_name}='{attr_value}'")
            
            # Combine conditions with 'and'
            xpath = "//" + (element_type if element_type != '' else "*")
            if conditions:
                xpath += "[" + " and ".join(conditions) + "]"
            
            logger.info(f"Looking for elements with XPath: {xpath}")
            elements = driver.find_elements(By.XPATH, xpath)
        
        # Check if we found exactly one element
        if len(elements) == 0:
            criteria_str = []
            if text != '':
                criteria_str.append(f"text='{text}'")
            if class_name != '':
                criteria_str.append(f"class='{class_name}'")
            if id != '':
                criteria_str.append(f"id='{id}'")
            if element_type != '':
                criteria_str.append(f"element_type='{element_type}'")
            for attr_name, attr_value in attributes.items():
                criteria_str.append(f"{attr_name}='{attr_value}'")
            if xpath != '':
                criteria_str.append(f"xpath='{xpath}'")
            
            error_msg = f"No elements found matching criteria: {', '.join(criteria_str)}"
            logger.error(error_msg)
            
            # Switch back to original context before returning
            if not original_context:
                driver.switch_to.default_content()
                
            return error_msg
        
        if len(elements) > 1:
            error_msg = f"Found {len(elements)} elements matching the criteria. Please provide more specific criteria."
            logger.error(error_msg)
            
            # Switch back to original context before returning
            if not original_context:
                driver.switch_to.default_content()
                
            return error_msg
        
        # Get the element
        element = elements[0]
        
        # If return_html is True, return the HTML content instead of JSON
        if return_html:
            try:
                # Get innerHTML or outerHTML
                inner_html = element.get_attribute("innerHTML")
                outer_html = element.get_attribute("outerHTML")
                
                # Switch back to original context
                if not original_context:
                    driver.switch_to.default_content()
                
                return json.dumps({
                    "innerHTML": inner_html,
                    "outerHTML": outer_html
                })
                
            except Exception as html_e:
                error_msg = f"Error getting HTML content: {str(html_e)}"
                logger.error(error_msg)
                
                # Switch back to original context in case of error
                if not original_context:
                    driver.switch_to.default_content()
                
                return error_msg
        
        # Get style information
        style_info = {}
        
        try:
            # Get basic element info first
            tag_name = element.tag_name
            element_id = element.get_attribute("id") or "no-id"
            element_class = element.get_attribute("class") or "no-class"
            element_text = element.text[:50] + "..." if len(element.text) > 50 else element.text
            
            style_info.update({
                "element_info": {
                    "tag_name": tag_name,
                    "id": element_id,
                    "class": element_class,
                    "text": element_text,
                    "xpath": xpath,
                    "in_iframe_id": in_iframe_id,
                    "in_iframe_name": in_iframe_name
                }
            })
            
            # Get all styles (equivalent to Styles tab in Chrome dev tools)
            if all_styles:
                # Get inline styles
                inline_style = element.get_attribute("style") or ""
                
                # Use JavaScript to get all applied styles
                all_styles_script = """
                var element = arguments[0];
                var styles = {};
                var styleSheets = document.styleSheets;
                
                // Get inline styles
                var inlineStyle = element.getAttribute('style') || '';
                
                // Get styles from CSS rules
                var appliedRules = [];
                for (var i = 0; i < styleSheets.length; i++) {
                    try {
                        var rules = styleSheets[i].cssRules || styleSheets[i].rules;
                        for (var j = 0; j < rules.length; j++) {
                            try {
                                if (element.matches(rules[j].selectorText)) {
                                    appliedRules.push({
                                        selector: rules[j].selectorText,
                                        cssText: rules[j].style.cssText,
                                        href: styleSheets[i].href || 'inline'
                                    });
                                }
                            } catch (e) {
                                // Skip rules that can't be processed
                            }
                        }
                    } catch (e) {
                        // Skip stylesheets that can't be accessed (CORS)
                    }
                }
                
                return {
                    inline: inlineStyle,
                    appliedRules: appliedRules
                };
                """
                
                try:
                    all_styles_result = driver.execute_script(all_styles_script, element)
                    style_info["all_styles"] = all_styles_result
                except Exception as e:
                    logger.warning(f"Could not get all styles: {str(e)}")
                    style_info["all_styles"] = {
                        "inline": inline_style,
                        "appliedRules": [],
                        "error": f"Could not retrieve CSS rules: {str(e)}"
                    }
            
            # Get computed styles (equivalent to Computed tab in Chrome dev tools)
            if computed_style:
                # List of common CSS properties to check
                common_properties = [
                    'display', 'position', 'top', 'right', 'bottom', 'left',
                    'width', 'height', 'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
                    'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
                    'border', 'border-width', 'border-style', 'border-color',
                    'background', 'background-color', 'background-image', 'background-position', 'background-size',
                    'color', 'font-family', 'font-size', 'font-weight', 'font-style',
                    'text-align', 'text-decoration', 'line-height', 'letter-spacing',
                    'opacity', 'visibility', 'overflow', 'z-index', 'float', 'clear',
                    'box-sizing', 'flex', 'flex-direction', 'justify-content', 'align-items'
                ]
                
                computed_styles_script = """
                var element = arguments[0];
                var properties = arguments[1];
                var computedStyle = window.getComputedStyle(element);
                var result = {};
                
                properties.forEach(function(prop) {
                    try {
                        result[prop] = computedStyle.getPropertyValue(prop);
                    } catch (e) {
                        result[prop] = '';
                    }
                });
                
                return result;
                """
                
                try:
                    computed_styles_result = driver.execute_script(computed_styles_script, element, common_properties)
                    style_info["computed_styles"] = computed_styles_result
                except Exception as e:
                    logger.warning(f"Could not get computed styles: {str(e)}")
                    style_info["computed_styles"] = {"error": f"Could not retrieve computed styles: {str(e)}"}
        
        except Exception as e:
            logger.error(f"Error getting style information: {str(e)}")
            style_info["error"] = f"Error getting style information: {str(e)}"
        
        # Switch back to original context
        if not original_context:
            driver.switch_to.default_content()
            
        return json.dumps(style_info)
    
    except Exception as e:
        error_msg = f"Error finding element or getting styles: {str(e)}"
        logger.error(error_msg)
        
        # Switch back to original context in case of error
        try:
            if 'original_context' in locals() and not original_context:
                driver.switch_to.default_content()
        except:
            pass
            
        return error_msg
