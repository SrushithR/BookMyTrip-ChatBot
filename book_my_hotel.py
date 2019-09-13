"""
Lambda function for the validation and fulfillment of the BookMyTrip chat bot
"""
import datetime
import json

from response_methods import *
from validator_methods import *


def safe_int(n):
    """
    Safely convert n value to int.
    """
    if n is not None:
        return int(n)
    return n


def build_validation_result(isvalid, violated_slot, message_content):
    return {
        'isValid': isvalid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def generate_hotel_price(location, nights, room_type):
    """
    Generates a number within a reasonable range that might be expected for a hotel.
    The price is fixed for a pair of location and roomType.
    """

    room_types = ['queen', 'king', 'deluxe']
    cost_of_living = 0
    for i in range(len(location)):
        cost_of_living += ord(location.lower()[i]) - 97

    return nights * (100 + cost_of_living + (100 + room_types.index(room_type.lower())))


def validate_hotel(slots):
    """
        Function to validate the input for booking a hotel
    :param slots: all the required information for booking a hotel
    :return: validity of the input
    """
    location = slots['Location']
    checkin_date = slots['CheckInDate']
    nights = safe_int(slots['Nights'])
    room_type = slots['RoomType']

    if location and not isvalid_city(location):
        return build_validation_result(
            False,
            'Location',
            'We currently do not support {} as a valid destination. Can you try a different city?'.format(location)
        )

    if checkin_date:
        if not isvalid_date(checkin_date):
            return build_validation_result(False, 'CheckInDate',
                                           'I did not understand your check in date. When would you like to check in?')
        if datetime.datetime.strptime(checkin_date, '%Y-%m-%d').date() <= datetime.date.today():
            return build_validation_result(False, 'CheckInDate',
                                           'Reservations must be scheduled at least one day in advance. '
                                           'Can you try a different date?')

    if nights is not None and (nights < 1 or nights > 30):
        return build_validation_result(
            False,
            'Nights',
            'You can make a reservations for from one to thirty nights. How many nights would you like to stay for?'
        )

    if room_type and not isvalid_room_type(room_type):
        return build_validation_result(False, 'RoomType',
                                       'I did not recognize that room type. '
                                       'Would you like to stay in a queen, king, or deluxe room?')

    return {'isValid': True}


def book_hotel(intent_request):
    """
        Function to book a hotel based on the inputs from Lex
    :param intent_request: input received from the chatbot
    """
    slot_details = intent_request['currentIntent']['slots']

    # extracting the slot details from the input
    location = slot_details['Location'] if 'Location' in slot_details.keys() else None
    checkin_date = slot_details['CheckInDate'] if 'CheckInDate' in slot_details.keys() else None
    nights = safe_int(slot_details['Nights']) if 'Nights' in slot_details.keys() else None
    room_type = slot_details['RoomType'] if 'RoomType' in slot_details.keys() else None

    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    # Load confirmation history and track the current reservation.
    reservation = json.dumps({
        'ReservationType': 'Hotel',
        'Location': location,
        'RoomType': room_type,
        'CheckInDate': checkin_date,
        'Nights': nights
    })

    session_attributes['currentReservation'] = reservation

    if intent_request['invocationSource'] == 'DialogCodeHook':
        validation_result = validate_hotel(slot_details)
        if not validation_result['isValid']:
            slots = intent_request['currentIntent']['slots']
            slots[validation_result['violatedSlot']] = None

            return elicit_slot(
                session_attributes,
                intent_request['currentIntent']['name'],
                slots,
                validation_result['violatedSlot'],
                validation_result['message']
            )

        # Otherwise, let native DM rules determine how to elicit for slots and prompt for confirmation.  Pass price
        # back in sessionAttributes once it can be calculated; otherwise clear any setting from sessionAttributes.
        if location and checkin_date and nights and room_type:
            # The price of the hotel has yet to be confirmed.
            price = generate_hotel_price(location, nights, room_type)
            session_attributes['currentReservationPrice'] = price
        else:
            try:
                session_attributes.pop('currentReservationPrice')
            except:
                print('currentReservationPrice is not in the session attributes yet')

        session_attributes['currentReservation'] = reservation
        return delegate(session_attributes, intent_request['currentIntent']['slots'])

    # Booking the hotel.  In a real application, this would likely involve a call to a backend service.
    print('bookHotel under={}'.format(reservation))

    try:
        session_attributes.pop('currentReservationPrice')
        session_attributes.pop('currentReservation')
    except:
        print('nothing to delete from the session attributes')
    session_attributes['lastConfirmedReservation'] = reservation

    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Thanks, I have placed your reservation.   Please let me know if you would like to book a car '
                       'rental, or another hotel.'
        }
    )


def lambda_handler(event, context):
    """
        Entry function in AWS Lambda
    :param event: input to the lambda function
    """
    print('input received from Lex:', event)
    print('check_intent userId={}, intentName={}'.format(event['userId'],
                                                         event['currentIntent']['name']))

    intent_name = event['currentIntent']['name']

    if intent_name == 'BookHotel':
        return book_hotel(event)


if __name__ == '__main__':
    input_to_lambda = {
        "messageVersion": "1.0",
        "invocationSource": "DialogCodeHook",
        "userId": "John",
        "sessionAttributes": {},
        "bot": {
            "name": "BookTrip",
            "alias": "$LATEST",
            "version": "$LATEST"
        },
        "outputDialogMode": "Text",
        "currentIntent": {
            "name": "BookHotel",
            "slots": {
                "Location": "Chicago",
                "CheckInDate": "2030-11-08",
                "Nights": 4,
                "RoomType": "queen"
            },
            "confirmationStatus": "None"
        }
    }

    print(lambda_handler(input_to_lambda, ''))
