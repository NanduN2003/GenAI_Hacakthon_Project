document.addEventListener('DOMContentLoaded', function() {
    // --- DOM Element Selection ---
    const chatbotIcon = document.getElementById('chatbot-icon');
    const chatbotPopup = document.getElementById('chatbot-popup');
    const closeChatbotButton = document.getElementById('close-chatbot');
    
    const imageUploader = document.getElementById('imageUploader');
    const attachButton = document.getElementById('attach-button');
    const sendButton = document.getElementById('send-button');
    
    const chatMessages = document.getElementById('chat-messages');
    const fileNameSpan = document.getElementById('file-name');
    
    const attachmentContainer = document.getElementById('attachment-container');
    const companyInputContainer = document.getElementById('company-input-container');
    const companyNameInput = document.getElementById('company-name-input');

    const chatHeader = document.getElementById('chat-header');
    const resizer = document.getElementById('resizer');
    const toggleMaximize = document.getElementById('toggle-maximize');
    const sizePresets = document.getElementById('size-presets');

    // --- State Management ---
    let chatState = 'awaiting_image'; // Can be 'awaiting_image' or 'awaiting_company_name'
    let uploadedFileId = null;

    // --- Helper Functions ---
    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function addMessage(sender, text) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `${sender}-message`);
        messageElement.innerHTML = text;
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return messageElement;
    }

    function resetChatInput() {
        console.log("Resetting chat state");
        chatState = 'awaiting_image';
        uploadedFileId = null;
        
        // Clear inputs
        imageUploader.value = '';
        fileNameSpan.textContent = 'No file chosen';
        companyNameInput.value = '';

        // Reset UI visibility and state
        attachmentContainer.classList.remove('hidden');
        companyInputContainer.classList.add('hidden');
        sendButton.disabled = false;
        companyNameInput.disabled = false;
    }

    // --- Core Logic Functions ---

    function handleImageUpload() {
        const file = imageUploader.files[0];
        if (!file) {
            addMessage('bot', 'Please select an image first by clicking the paperclip icon.');
            return;
        }

        addMessage('user', `Uploaded: ${file.name}`);
        const botMessage = addMessage('bot', '<em>Uploading file...</em>');

        const formData = new FormData();
        formData.append('file', file);

        fetch('/uploadfile/', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`File upload failed: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.file_id) {
                // --- Transition to next state ---
                uploadedFileId = data.file_id;
                chatState = 'awaiting_company_name';
                
                // Update UI for next step
                attachmentContainer.classList.add('hidden');
                companyInputContainer.classList.remove('hidden');
                companyNameInput.focus();
                
                botMessage.innerHTML = 'Thank you. Now, please enter the company name and press Send.';
            } else {
                throw new Error('Did not receive a file ID.');
            }
        })
        .catch(error => {
            botMessage.innerHTML = `An error occurred: ${error.message}`;
            resetChatInput(); 
        });
    }

    function handleStartAnalysis() {
        const companyName = companyNameInput.value.trim();
        if (!uploadedFileId) {
            addMessage('bot', 'Something went wrong. Please start over by attaching the image again.');
            resetChatInput();
            return;
        }

        // --- Step to disable multiple submissuons ---
        sendButton.disabled = true;
        companyNameInput.disabled = true;

        const botMessage = addMessage('bot', '<em>Starting analysis...</em>');
        startStreaming(uploadedFileId, companyName, botMessage);
    }

    function startStreaming(fileId, companyName, botMessage) {
        const apiUrl = `/stream/${fileId}?company_name=${encodeURIComponent(companyName)}`;
        const eventSource = new EventSource(apiUrl);

        eventSource.onopen = function() {
            console.log('SSE connection opened');
        };

        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);

                if (data.error) {
                    let errorMessage = "An unexpected error occurred. Please try again.";
                    if (data.error_type === 'file_not_found') {
                        errorMessage = "Error: The file was not found or your session has expired. Please re-upload the image.";
                    } else if (data.error_type === 'invocation_error') {
                        errorMessage = `Sorry, the AI analysis failed. Please check the image or try a different one. Details: ${data.details || ''}`;
                    } else if (data.error) {
                        errorMessage = `Sorry, I encountered an error: ${data.error}`;
                    }
                    botMessage.innerHTML = ''; 
                    botMessage.appendChild(document.createTextNode(errorMessage));
                    eventSource.close();
                    resetChatInput();
                } else if (data.status) {
                    botMessage.innerHTML = `<em>${data.status}</em>`;
                } else {
                    
                    const { intent, flight_details, insights_from_history, additional_service_info } = data;

                    const intentText = `Intent: ${intent ? intent.replace(/_/g, ' ') : 'N/A'}`;
                    
                    const responseContainer = h('div', { class: 'response-container' });
                    responseContainer.appendChild(h('p', {}, [intentText]));

                    const renderedFlightDetails = renderFlightDetails(flight_details);
                    if (renderedFlightDetails) responseContainer.appendChild(renderedFlightDetails);

                    const grid = h('div', { class: 'response-grid' });
                    const renderedInsights = renderInsights(insights_from_history);
                    const renderedServiceInfo = renderServiceInfo(additional_service_info);
                    if (renderedInsights) grid.appendChild(renderedInsights);
                    if (renderedServiceInfo) grid.appendChild(renderedServiceInfo);
                    if(grid.hasChildNodes()) responseContainer.appendChild(grid);

                    const renderedNotes = renderNotes(flight_details);
                    if (renderedNotes) responseContainer.appendChild(renderedNotes);

                    botMessage.innerHTML = ''; 
                    botMessage.appendChild(responseContainer);
                    
                    // --- Human-in-the-Loop: Ask for confirmation in a new message ---
                    if (flight_details && flight_details.origin_iata && flight_details.destination_iata) {
                        promptForFlightSearch(flight_details, insights_from_history);
                    }
                    
                    eventSource.close();
                    resetChatInput();
                }
            } catch (e) {
                console.error('Failed to parse SSE data', e, event.data);
                botMessage.textContent = 'There was an issue processing the response.';
                eventSource.close();
                resetChatInput();
            }
        };

        eventSource.onerror = function(err) {
            console.error('EventSource failed:', err);
            botMessage.innerHTML = 'An unexpected error occurred while streaming the response.';
            eventSource.close();
            resetChatInput(); // Resets the chat in any error occurnece
        };
    }

    function promptForFlightSearch(flightDetails, insights) {
        const promptMessage = addMessage('bot', ''); 

        const confirmationContainer = h('div', { class: 'confirmation-container' });
        confirmationContainer.appendChild(h('p', {}, ['Would you like to search for flights with these details?']));
        
        const yesButton = h('button', { class: 'btn-confirm' }, ['Yes, find flights']);
        const noButton = h('button', { class: 'btn-cancel' }, ['No, thanks']);
        
        confirmationContainer.appendChild(yesButton);
        confirmationContainer.appendChild(noButton);
        promptMessage.appendChild(confirmationContainer);

        yesButton.addEventListener('click', () => {
            yesButton.disabled = true;
            noButton.disabled = true;
            promptMessage.innerHTML = '<em>Searching for flights... Please wait.</em>';
            handleFlightSearch(flightDetails, insights, promptMessage);
        });

        noButton.addEventListener('click', () => {
            promptMessage.innerHTML = '<em>Ok, let me know if you need anything else!</em>';
        });
    }

    function handleFlightSearch(flightDetails, insights, promptMessage) {
        const payload = {
            flight_details: flightDetails,
            hotel_preferences: (insights && insights.hotel_preferences) ? insights.hotel_preferences : null
        };

        fetch('/find_flights/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    
                    let errorMessage = 'Flight search failed.';
                    if (err.detail && Array.isArray(err.detail)) {
                        
                        errorMessage = err.detail.map(e => `Error in field '${e.loc.join(' -> ')}': ${e.msg}`).join('; ');
                    } else if (err.detail) {
                        errorMessage = JSON.stringify(err.detail);
                    }
                    throw new Error(errorMessage);
                });
            }
            return response.json();
        })
        .then(data => {
            // Guve the prompt message in new text/message
            promptMessage.innerHTML = '<em>Search complete. Here are the top flight offers I found:</em>';
            renderFlightOffers(data.offers);
            // If hotel recommendations are provided, then show as a separate message
            if (data.hotel_recommendations && data.hotel_recommendations.length) {
                renderHotelRecommendations(data.hotel_recommendations);
            }
            resetChatInput();
        })
        .catch(error => {
            promptMessage.innerHTML = `<p class="error">An error occurred during the flight search: ${error.message}</p>`;
            resetChatInput();
        });
    }

    function renderFlightOffers(offers) {
        if (!offers || offers.length === 0) {
            addMessage('bot', 'Sorry, no flight offers were found for your request.');
            return;
        }

        
        const offersMessage = addMessage('bot', '');

        const offersContainer = h('div', { class: 'response-section' });
        offersContainer.appendChild(h('h5', {}, ['Flight Recommendations']));

        const offersList = h('div', { class: 'offers-grid' }); 
        
        offers.forEach(offer => {
            const price = offer.price.total;
            const currency = offer.price.currency;
            
            const offerCard = h('div', { class: 'offer-card' });

            const cardHeader = h('div', { class: 'offer-card-header' }, [
                h('span', {class: 'offer-price-label'}, ['Total Price']),
                h('span', { class: 'offer-price-value' }, [`${price} ${currency}`])
            ]);
            offerCard.appendChild(cardHeader);

            const deal = offer.deal;
            if (deal && deal.text) {
                const dealBadge = h('div', { class: `deal-badge deal-${deal.score}` }, [deal.text]);
                cardHeader.appendChild(dealBadge);
            }

            const cardBody = h('div', { class: 'offer-card-body' });
            offer.itineraries.forEach((itinerary, index) => {
                const itineraryElement = h('div', { class: 'itinerary' });
                
                const itineraryType = itinerary.segments.length > 1 ? 'Connecting Flight' : 'Direct Flight';
                const itineraryTitleText = `Itinerary ${index + 1}: ${itineraryType}`;
                const itineraryTitle = h('h6', {}, [itineraryTitleText]);
                itineraryElement.appendChild(itineraryTitle);

                const segmentsList = h('ul', { class: 'segments-list' });
                itinerary.segments.forEach(segment => {
                    const departureTime = new Date(segment.departure.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    const arrivalTime = new Date(segment.arrival.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                    const segmentElement = h('li', { class: 'segment-item'}, [
                        h('div', {class: 'segment-airline'}, [`${segment.carrierCode} ${segment.number}`]),
                        h('div', {class: 'segment-airports'}, [
                            h('strong', {}, segment.departure.iataCode),
                            ' → ',
                            h('strong', {}, segment.arrival.iataCode)
                        ]),
                        h('div', {class: 'segment-times'}, [`${departureTime} - ${arrivalTime}`])
                    ]);
                    segmentsList.appendChild(segmentElement);
                });
                itineraryElement.appendChild(segmentsList);
                cardBody.appendChild(itineraryElement);
            });
            offerCard.appendChild(cardBody);
            offersList.appendChild(offerCard);
        });

        offersContainer.appendChild(offersList);
        offersMessage.appendChild(offersContainer); // Appendw to new messgae
    }

    function renderHotelRecommendations(hotels) {
        if (!hotels || hotels.length === 0) return;
        const hotelsMessage = addMessage('bot', '');

        const hotelsContainer = h('div', { class: 'response-section' });
        hotelsContainer.appendChild(h('h5', {}, ['Hotel Recommendations']));

        const list = h('ul', { class: 'hotel-list' });
        hotels.forEach(hotel => {
            const item = h('li', { class: 'hotel-item' });
            const name = hotel.name || hotel.hotelName || 'Unknown Hotel';
            const address = (hotel.address && hotel.address.lines && hotel.address.lines[0]) ? hotel.address.lines[0] : (hotel.address && hotel.address.cityName) || '';
            item.appendChild(h('strong', {}, [name]));
            if (address) item.appendChild(h('div', { class: 'hotel-address' }, [address]));
            list.appendChild(item);
        });

        hotelsContainer.appendChild(list);
        hotelsMessage.appendChild(hotelsContainer);
    }

    // --- DOM Helper Function ---
    function h(tag, attributes = {}, children = []) {
        const element = document.createElement(tag);
        for (const key in attributes) {
            element.setAttribute(key, attributes[key]);
        }
        // Ensure children is always an array to handle single or multiple children
        const childArray = Array.isArray(children) ? children : [children];
        
        childArray.forEach(child => {
            if (child) { 
                if (typeof child === 'string' || typeof child === 'number') {
                    element.appendChild(document.createTextNode(child));
                } else {
                    element.appendChild(child);
                }
            }
        });
        return element;
    }

    // --- Rendering Helper Functions for Structured Data ---

    function renderFlightDetails(details) {
        if (!details) return null;
        return h('div', { class: 'response-section' }, [
            h('h5', {}, ['Flight Details']),
            h('ul', { class: 'details-list' }, [
                h('li', {}, [`Origin: ${details.origin || 'N/A'} (${details.origin_iata || 'N/A'})`]),
                h('li', {}, [`Destination: ${details.destination || 'N/A'} (${details.destination_iata || 'N/A'})`]),
                h('li', {}, [`Departure: ${details.departure_date || 'N/A'}`]),
                h('li', {}, [`Return: ${details.return_date || 'N/A'}`]),
                h('li', {}, [`Passengers: ${details.number_of_passengers || 'N/A'}`]),
                h('li', {}, [`Class of Service: ${details.class_of_service || 'N/A'}`]),
            ])
        ]);
    }

    function renderInsights(insights) {
        if (!insights) return null;
        const children = [h('h5', {}, ['Insights from History'])];
        const { airline_preferences, hotel_preferences, general_notes } = insights;

        if (airline_preferences) {
            const airlineItems = [];
            if (airline_preferences.airlines_opted && airline_preferences.airlines_opted.length) {
                airlineItems.push(h('li', {}, [`Airlines Opted: ${airline_preferences.airlines_opted.join(', ')}`]));
            }
            if (airline_preferences.alliance) {
                airlineItems.push(h('li', {}, [`Alliance: ${airline_preferences.alliance}`]));
            }
            if (airline_preferences.past_class_preference) {
                airlineItems.push(h('li', {}, [`Past Class: ${airline_preferences.past_class_preference}`]));
            }
            if (airlineItems.length > 0) {
                children.push(h('h6', {}, ['Airline Preferences']));
                children.push(h('ul', { class: 'details-list' }, airlineItems));
            }
        }

        if (hotel_preferences) {
            const hotelItems = [];
            if (hotel_preferences.preferred_chains && hotel_preferences.preferred_chains.length) {
                hotelItems.push(h('li', {}, [`Chains: ${hotel_preferences.preferred_chains.join(', ')}`]));
            }
            if (hotel_preferences.room_type) {
                hotelItems.push(h('li', {}, [`Room Type: ${hotel_preferences.room_type}`]));
            }
            if (hotelItems.length > 0) {
                children.push(h('h6', {}, ['Hotel Preferences']));
                children.push(h('ul', { class: 'details-list' }, hotelItems));
            }
        }

        if (general_notes) {
            children.push(h('p', {}, [h('strong', {}, ['General Notes: ']), escapeHtml(general_notes)]));
        }
        
        return h('div', { class: 'response-section' }, children);
    }

    function renderServiceInfo(serviceInfo) {
        if (!serviceInfo) return null;
        const items = [];
        if (serviceInfo.route_info) {
            items.push(h('li', {}, [h('strong', {}, ['Route Info: ']), escapeHtml(serviceInfo.route_info)]));
        }
        if (serviceInfo.class_policy) {
            items.push(h('li', {}, [h('strong', {}, ['Class Policy: ']), escapeHtml(serviceInfo.class_policy)]));
        }
        if (serviceInfo.ground_transport_info) {
            items.push(h('li', {}, [h('strong', {}, ['Ground Transport: ']), escapeHtml(serviceInfo.ground_transport_info)]));
        }
        if (items.length === 0) return null;

        return h('div', { class: 'response-section' }, [
            h('h5', {}, ['Additional Service Info']),
            h('ul', { class: 'details-list' }, items)
        ]);
    }

    function renderNotes(flightDetails) {
        if (!flightDetails || (!flightDetails.notes && !flightDetails.agency_notes)) return null;
        const items = [];
        if (flightDetails.notes) {
            items.push(h('li', {}, [h('strong', {}, ['General: ']), escapeHtml(flightDetails.notes)]));
        }
        if (flightDetails.agency_notes) {
            items.push(h('li', {}, [h('strong', {}, ['Agency Notes: ']), escapeHtml(flightDetails.agency_notes)]));
        }
        if (items.length === 0) return null;

        return h('div', { class: 'response-section notes' }, [
            h('h5', {}, ['Notes']),
            h('ul', { class: 'details-list' }, items)
        ]);
    }

    // --- Event Listeners ---

    // Popup logic
    chatbotIcon.addEventListener('click', (e) => {
        e.stopPropagation(); 
        chatbotPopup.classList.remove('hidden');
        chatbotIcon.style.display = 'none';
        resetChatInput(); // Reset to initial state when opening
    });

    // If the pop-up is clicked then it would hide
    closeChatbotButton.addEventListener('click', () => {
        chatbotPopup.classList.add('hidden');
        chatbotIcon.style.display = 'block';
    });

    
    document.addEventListener('click', (e) => {
        
        if (!chatbotPopup.classList.contains('hidden') && e.target !== chatbotIcon && !chatbotPopup.contains(e.target)) {
            chatbotPopup.classList.add('hidden');
            chatbotIcon.style.display = 'block';
        }
    });

    
    chatbotPopup.addEventListener('click', (e) => {
        e.stopPropagation();
    });

    // Attach file button triggers the hidden file input
    attachButton.addEventListener('click', () => {
        imageUploader.click();
    });

    // Update file name when a file is chosen
    imageUploader.addEventListener('change', () => {
        if (imageUploader.files.length > 0) {
            fileNameSpan.textContent = imageUploader.files[0].name;
        } else {
            fileNameSpan.textContent = 'No file chosen';
        }
    });
    
    // Main "Send" button logic
    sendButton.addEventListener('click', () => {
        if (chatState === 'awaiting_image') {
            handleImageUpload();
        } else if (chatState === 'awaiting_company_name') {
            handleStartAnalysis();
        }
    });
    
    // Allow using Enter in the company name field
    companyNameInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            handleStartAnalysis();
        }
    });

    // --- Resizing Logic ---
    let isResizing = false;
    resizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', () => {
            isResizing = false;
            document.removeEventListener('mousemove', handleMouseMove);
        });
    });

    function handleMouseMove(e) {
        if (!isResizing) return;
        const newWidth = document.body.clientWidth - e.clientX;
        const newHeight = document.body.clientHeight - e.clientY;
        chatbotPopup.style.width = `${newWidth}px`;
        chatbotPopup.style.height = `${newHeight}px`;
    }

    if (toggleMaximize) {
        toggleMaximize.addEventListener('click', () => {
            chatbotPopup.classList.toggle('maximized');
        });
    }

    if (sizePresets) {
        sizePresets.addEventListener('click', (e) => {
            const btn = e.target.closest('button');
            if (!btn) return;
            let preset = btn.getAttribute('data-size');
            let width, height;
            if (preset && preset.includes('x')) {
                [width, height] = preset.split('x');
            } else {
                const dw = btn.getAttribute('data-width');
                const dh = btn.getAttribute('data-height');
                if (dw && dh) {
                    width = dw;
                    height = dh;
                } else {
                    const match = (btn.textContent || '').match(/(\d+)\s*x\s*(\d+)/i);
                    if (match) {
                        width = match[1];
                        height = match[2];
                    }
                }
            }
            if (!width || !height) {
                console.warn('Size preset button missing size data');
                return;
            }
            chatbotPopup.style.width = `${width}px`;
            chatbotPopup.style.height = `${height}px`;
            chatbotPopup.classList.remove('maximized');
        });
    }
});