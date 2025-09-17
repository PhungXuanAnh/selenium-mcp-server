"""
Element interaction tools for Selenium MCP server.

This module provides tools for finding and interacting with web page elements.
"""

import json
import logging
import time

from selenium.webdriver.common.by import By

# Import the global mcp instance from the main server module
from ..server import mcp, ensure_driver_initialized

logger = logging.getLogger(__name__)


@mcp.tool()
def get_an_element(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', in_iframe_id: str = '', in_iframe_name: str = '', return_html: bool = False, xpath: str = '') -> str:
    """Get an element identified by text content, class name, or ID.
    
    This tool finds an element based on specified criteria. At least one 
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
    
    Returns:
        A JSON string with information about the found element or an error message.
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
        
        # Get element properties for standard JSON response
        try:
            tag_name = element.tag_name
        except:
            tag_name = "unknown"
            
        try:
            element_id = element.get_attribute("id") or "no-id"
        except:
            element_id = "unknown"
            
        try:
            element_class = element.get_attribute("class") or "no-class"
        except:
            element_class = "unknown"
            
        try:
            element_text = element.text[:50] + "..." if len(element.text) > 50 else element.text
        except:
            element_text = "unknown"
            
        # Return element info as JSON
        element_info = {
            "found": True,
            "tag_name": tag_name,
            "id": element_id,
            "class": element_class,
            "text": element_text,
            "xpath": xpath,
            "in_iframe_id": in_iframe_id,
            "in_iframe_name": in_iframe_name
        }
        
        # Switch back to original context
        if not original_context:
            driver.switch_to.default_content()
            
        return json.dumps(element_info)
    
    except Exception as e:
        error_msg = f"Error finding element: {str(e)}"
        logger.error(error_msg)
        
        # Switch back to original context in case of error
        try:
            if 'original_context' in locals() and not original_context:
                driver.switch_to.default_content()
        except:
            pass
            
        return error_msg


@mcp.tool()
def get_elements(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', in_iframe_id: str = '', in_iframe_name: str = '', page: int = 1, page_size: int = 3, return_html: bool = False, xpath: str = '') -> str:
    """Get multiple elements identified by text content, class name, or ID with pagination.
    
    This tool finds elements based on specified criteria. At least one 
    of text, class_name, id, attributes, element_type, or xpath must be provided. Unlike get_an_element,
    this function returns multiple elements with pagination support.
    
    Args:
        text: Text content of the elements to find. Case-sensitive text matching.
        class_name: CSS class name of the elements to find.
        id: ID attribute of the elements to find.
        attributes: Dictionary of attribute name-value pairs to match (e.g. {'data-test': 'button'}).
        element_type: HTML element type to find (e.g. 'div', 'input', 'h1', 'button', etc.).
        in_iframe_id: ID of the iframe to search within. If provided, the function will switch to this iframe before searching.
        in_iframe_name: Name of the iframe to search within. If provided and in_iframe_id is not provided, the function will switch to this iframe before searching.
        page: Current page of elements returned in the response (default: 1).
        page_size: Number of elements to return in the response (default: 3).
        return_html: Return the HTML content of the elements instead of JSON information.
        xpath: Direct XPath selector to find the elements. When provided, other selection criteria are ignored.
    
    Returns:
        A JSON string with information about the found elements or an error message.
        If return_html is True, includes HTML content of the elements.
    """
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    if text == '' and class_name == '' and id == '' and not attributes and element_type == '' and xpath == '':
        return "Error: At least one of text, class_name, id, attributes, element_type, or xpath must be provided"
    
    # Validate pagination parameters
    if page < 1:
        return "Error: Page must be at least 1"
    if page_size < 1:
        return "Error: Page size must be at least 1"
    
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
            all_elements = driver.find_elements(By.XPATH, xpath)
            search_xpath = xpath
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
            search_xpath = "//" + (element_type if element_type != '' else "*")
            if conditions:
                search_xpath += "[" + " and ".join(conditions) + "]"
            
            logger.info(f"Looking for elements with XPath: {search_xpath}")
            all_elements = driver.find_elements(By.XPATH, search_xpath)
        
        total_elements = len(all_elements)
        total_pages = (total_elements + page_size - 1) // page_size if total_elements > 0 else 1
        
        # Check if we found any elements
        if total_elements == 0:
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
                
            return json.dumps({
                "found": False,
                "error": error_msg,
                "total_elements": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "elements": []
            })
        
        # Calculate pagination indices
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_elements)
        
        # Check if the requested page is valid
        if start_idx >= total_elements:
            error_msg = f"Page {page} exceeds total available pages ({total_pages})"
            logger.error(error_msg)
            
            # Switch back to original context before returning
            if not original_context:
                driver.switch_to.default_content()
                
            return json.dumps({
                "found": True,
                "error": error_msg,
                "total_elements": total_elements,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "elements": []
            })
        
        # Get the paginated elements
        paginated_elements = all_elements[start_idx:end_idx]
        elements_info = []
        
        # Process each element
        for i, element in enumerate(paginated_elements):
            # Generate a unique XPath for this specific element
            try:
                unique_xpath = driver.execute_script("""
                function getPathTo(element) {
                    if (element.id !== '')
                        return '//*[@id="' + element.id + '"]';
                    if (element === document.body)
                        return '/html/body';

                    var ix = 0;
                    var siblings = element.parentNode.childNodes;
                    for (var i = 0; i < siblings.length; i++) {
                        var sibling = siblings[i];
                        if (sibling === element)
                            return getPathTo(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                        if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                            ix++;
                    }
                }
                return getPathTo(arguments[0]);
                """, element)
            except:
                # Fallback if JS execution fails
                unique_xpath = f"{search_xpath}[{i + 1}]"
                
            if return_html:
                # Get HTML content for this element
                try:
                    inner_html = element.get_attribute("innerHTML")
                    outer_html = element.get_attribute("outerHTML")
                    
                    elements_info.append({
                        "innerHTML": inner_html,
                        "outerHTML": outer_html,
                        "uniqueXPath": unique_xpath
                    })
                except Exception as html_e:
                    elements_info.append({
                        "error": f"Error getting HTML: {str(html_e)}",
                        "innerHTML": "",
                        "outerHTML": "",
                        "uniqueXPath": unique_xpath
                    })
            else:
                # Get standard element info
                try:
                    tag_name = element.tag_name
                except:
                    tag_name = "unknown"
                    
                try:
                    element_id = element.get_attribute("id") or "no-id"
                except:
                    element_id = "unknown"
                    
                try:
                    element_class = element.get_attribute("class") or "no-class"
                except:
                    element_class = "unknown"
                    
                try:
                    element_text = element.text[:50] + "..." if len(element.text) > 50 else element.text
                except:
                    element_text = "unknown"
                
                elements_info.append({
                    "tag_name": tag_name,
                    "id": element_id,
                    "class": element_class,
                    "text": element_text,
                    "uniqueXPath": unique_xpath
                })
        
        # Return elements info as JSON
        result = {
            "found": True,
            "total_elements": total_elements,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "elements": elements_info,
            "xpath": search_xpath,
            "in_iframe_id": in_iframe_id,
            "in_iframe_name": in_iframe_name
        }
        
        # Switch back to original context
        if not original_context:
            driver.switch_to.default_content()
            
        return json.dumps(result)
    
    except Exception as e:
        error_msg = f"Error finding elements: {str(e)}"
        logger.error(error_msg)
        
        # Switch back to original context in case of error
        try:
            if 'original_context' in locals() and not original_context:
                driver.switch_to.default_content()
        except:
            pass
            
        return json.dumps({
            "found": False,
            "error": error_msg,
            "total_elements": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "elements": []
        })


@mcp.tool()
def click_to_element(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', in_iframe_id: str = '', in_iframe_name: str = '', element_index: int = -1, xpath: str = '') -> str:
    """Click on an element identified by text content, class name, or ID.
    
    This tool finds and clicks on an element based on specified criteria. At least one 
    of text, class_name, id, attributes, element_type, or xpath must be provided. If multiple elements match the criteria, 
    or if no elements are found, an error message is returned.
    
    Args:
        text: Text content of the element to click. Case-sensitive text matching.
        class_name: CSS class name of the element to click.
        id: ID attribute of the element to click.
        attributes: Dictionary of attribute name-value pairs to match (e.g. {'data-test': 'button'}).
        element_type: HTML element type to find (e.g. 'div', 'input', 'h1', 'button', etc.).
        in_iframe_id: ID of the iframe to search within. If provided, the function will switch to this iframe before searching.
        in_iframe_name: Name of the iframe to search within. If provided and in_iframe_id is not provided, the function will switch to this iframe before searching.
        element_index: Index of the element to click if multiple elements match the criteria. Default is -1 (don't use this parameter).
        xpath: Direct XPath selector to find the element. When provided, other selection criteria are ignored.
    
    Returns:
        A message indicating whether the click was successful or an error message.
    """
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        # Store current URL before the click
        current_url = driver.current_url
        
        if element_index >= 0:
            # Use get_elements to get multiple elements if index is specified
            logger.info(f"Using element_index {element_index} to select from multiple matching elements")
            elements_info = get_elements(text, class_name, id, attributes, element_type, 
                                        in_iframe_id, in_iframe_name, 
                                        page=1, page_size=max(element_index+1, 3),
                                        return_html=False, xpath=xpath)
            
            # Parse the JSON result
            try:
                elements_data = json.loads(elements_info)
                
                # Check if elements were found
                if not isinstance(elements_data, dict) or not elements_data.get("found", False):
                    return elements_info  # Return the error message from get_elements
                
                total_elements = elements_data.get("total_elements", 0)
                
                if total_elements == 0:
                    return f"No elements found matching the given criteria"
                
                if element_index >= total_elements:
                    return f"Index {element_index} is out of bounds. Only {total_elements} elements were found."
                
                # Get all elements matching the criteria using XPath
                elements_xpath = elements_data.get("xpath", "")
                elements_iframe_id = elements_data.get("in_iframe_id", "")
                elements_iframe_name = elements_data.get("in_iframe_name", "")
                
                # Switch to iframe if needed
                original_context = True
                if elements_iframe_id or elements_iframe_name:
                    try:
                        if elements_iframe_id:
                            iframe = driver.find_element(By.ID, elements_iframe_id)
                            driver.switch_to.frame(iframe)
                        elif elements_iframe_name:
                            driver.switch_to.frame(elements_iframe_name)
                        original_context = False
                    except Exception as iframe_e:
                        return f"Error switching to iframe for clicking: {str(iframe_e)}"
                
                # Find all matching elements
                all_elements = driver.find_elements(By.XPATH, elements_xpath)
                
                # Get the element at the specified index
                target_element = all_elements[element_index]
                
                # Get element info for the log message
                element_tag = target_element.tag_name
                element_id = target_element.get_attribute("id") or "no-id"
                element_class = target_element.get_attribute("class") or "no-class"
                element_text = target_element.text[:50] + "..." if len(target_element.text) > 50 else target_element.text
                
                # Click the target element
                target_element.click()
                
                # Wait a moment for any navigation to start
                time.sleep(0.5)
                
                # Switch back to default content
                if not original_context:
                    driver.switch_to.default_content()
                
                # Check if the URL has changed, indicating navigation occurred
                new_url = driver.current_url
                if new_url != current_url:
                    return f"Successfully clicked on element at index {element_index} which triggered navigation from {current_url} to {new_url}"
                
                # If no navigation occurred, return the standard success message
                return f"Successfully clicked on {element_tag} element at index {element_index} with id='{element_id}', class='{element_class}', text='{element_text}'"
                
            except (json.JSONDecodeError, IndexError, Exception) as e:
                return f"Error selecting element at index {element_index}: {str(e)}"
        else:
            # Use the original behavior when element_index is -1
            # Get element using the get_element function
            element_info = get_an_element(text, class_name, id, attributes, element_type, 
                                       in_iframe_id, in_iframe_name, 
                                       return_html=False, xpath=xpath)
            
            # Parse the JSON result
            try:
                element_data = json.loads(element_info)
                
                # Check if the element was found
                if not isinstance(element_data, dict) or not element_data.get("found", False):
                    return element_info  # Return the error message from get_element
                    
                single_tag_name = element_data.get("tag_name", "unknown")
                single_element_id = element_data.get("id", "unknown")
                single_element_class = element_data.get("class", "unknown")
                single_element_text = element_data.get("text", "")
                single_xpath = element_data.get("xpath", "")
                single_iframe_id = element_data.get("in_iframe_id", "")
                single_iframe_name = element_data.get("in_iframe_name", "")
                
                # Switch to iframe if needed
                original_context = True
                if single_iframe_id or single_iframe_name:
                    try:
                        if single_iframe_id:
                            iframe = driver.find_element(By.ID, single_iframe_id)
                            driver.switch_to.frame(iframe)
                        elif single_iframe_name:
                            driver.switch_to.frame(single_iframe_name)
                        original_context = False
                    except Exception as iframe_e:
                        return f"Error switching to iframe for clicking: {str(iframe_e)}"
                
                # Find the element again using the same xpath
                element = driver.find_element(By.XPATH, single_xpath)
                
            except json.JSONDecodeError:
                # get_element returned an error message, not JSON
                return element_info
            
            # Now click the element
            element.click()
            
            # Wait a moment for any navigation to start
            time.sleep(0.5)
            
            # Switch back to default content
            if not original_context:
                driver.switch_to.default_content()
            
            # Check if the URL has changed, indicating navigation occurred
            new_url = driver.current_url
            if new_url != current_url:
                return f"Successfully clicked on {single_tag_name} element which triggered navigation from {current_url} to {new_url}"
            
            # If no navigation occurred, return the standard success message
            return f"Successfully clicked on {single_tag_name} element with id='{single_element_id}', class='{single_element_class}', text='{single_element_text}'"
    
    except Exception as e:
        error_msg = f"Error clicking element: {str(e)}"
        logger.error(error_msg)
        
        # Switch back to default content in case of error
        try:
            if 'original_context' in locals() and not original_context:
                driver.switch_to.default_content()
        except:
            pass
        
        # Check if navigation occurred despite the error
        try:
            new_url = driver.current_url
            if 'current_url' in locals() and new_url != current_url:
                return f"Click succeeded with navigation to {new_url}, but encountered error when reporting: {str(e)}"
        except:
            pass
            
        return error_msg


@mcp.tool()
def set_value_to_input_element(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', input_value: str = '', in_iframe_id: str = '', in_iframe_name: str = '', xpath: str = '') -> str:
    """Set a value to an input element identified by text content, class name, or ID.
    
    This tool finds an input element based on specified criteria and sets the provided value. At least one 
    of text, class_name, id, attributes, element_type, or xpath must be provided. If multiple elements match the criteria, 
    or if no elements are found, an error message is returned.
    
    Args:
        text: Text content of the element to find. Case-sensitive text matching.
        class_name: CSS class name of the element to find.
        id: ID attribute of the element to find.
        attributes: Dictionary of attribute name-value pairs to match (e.g. {'data-test': 'input'}).
        element_type: HTML element type to find (e.g. 'input', 'textarea', 'select', etc.).
        input_value: The value to set on the input element.
        in_iframe_id: ID of the iframe to search within. If provided, the function will switch to this iframe before searching.
        in_iframe_name: Name of the iframe to search within. If provided and in_iframe_id is not provided, the function will switch to this iframe before searching.
        xpath: Direct XPath selector to find the element. When provided, other selection criteria are ignored.
    
    Returns:
        A message indicating whether setting the value was successful or an error message.
    """
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        # Get element using the get_element function
        element_info = get_an_element(text, class_name, id, attributes, element_type, in_iframe_id, in_iframe_name, False, xpath)
        
        # Parse the JSON result
        try:
            element_data = json.loads(element_info)
            
            # Check if the element was found
            if not isinstance(element_data, dict) or not element_data.get("found", False):
                return element_info  # Return the error message from get_element
                
            tag_name = element_data.get("tag_name", "unknown")
            element_id = element_data.get("id", "unknown")
            element_class = element_data.get("class", "unknown")
            xpath = element_data.get("xpath", "")
            iframe_id = element_data.get("in_iframe_id", "")
            iframe_name = element_data.get("in_iframe_name", "")
            
            # Switch to iframe if needed
            original_context = True
            if iframe_id or iframe_name:
                try:
                    if iframe_id:
                        iframe = driver.find_element(By.ID, iframe_id)
                        driver.switch_to.frame(iframe)
                    elif iframe_name:
                        driver.switch_to.frame(iframe_name)
                    original_context = False
                except Exception as iframe_e:
                    return f"Error switching to iframe for setting value: {str(iframe_e)}"
            
            # Find the element again using the same xpath
            element = driver.find_element(By.XPATH, xpath)
            
        except json.JSONDecodeError:
            # get_element returned an error message, not JSON
            return element_info
        
        # Check if element is an input-like element that can accept values
        input_like_tags = ['input', 'textarea', 'select']
        if tag_name and tag_name.lower() not in input_like_tags:
            # Switch back to default content before returning if needed
            if not original_context:
                driver.switch_to.default_content()
            return f"Error: Found element with tag '{tag_name}' is not an input-like element that can accept values"
        
        # Clear existing value
        element.clear()
        
        # Set the new value
        element.send_keys(input_value)
        
        # Verify the value was set (for most input types)
        current_value = element.get_attribute('value')
        
        # Switch back to default content
        if not original_context:
            driver.switch_to.default_content()
        
        return f"Successfully set value '{input_value}' to {tag_name} element with id='{element_id}', class='{element_class}'. Current value: '{current_value}'"
    
    except Exception as e:
        error_msg = f"Error setting value to element: {str(e)}"
        logger.error(error_msg)
        
        # Switch back to default content in case of error
        try:
            if 'original_context' in locals() and not original_context:
                driver.switch_to.default_content()
        except:
            pass
            
        return error_msg