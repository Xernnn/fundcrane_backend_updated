from flask import Blueprint, request, jsonify
import stripe
from app.config import Config

stripe.api_key = Config.STRIPE_SECRET_KEY
payments_bp = Blueprint('payments', __name__)

@payments_bp.route('/create-subscription-product', methods=['POST'])
def create_subscription_product():
    try:
        data = request.get_json()
        
        # Validate input
        amount = data.get('amount')  # Monthly amount in cents
        investment_amount = data.get('investmentAmount')  # Total investment amount in cents
        currency = data.get('currency', 'sgd')
        customer_name = data.get('customerName', '')

        if not amount or not investment_amount:
            return jsonify({'error': 'Amount and Investment Amount are required'}), 400

        # Create a Stripe Product for the investment
        product = stripe.Product.create(
            name=f"Investment Installment Plan - {customer_name}",
            metadata={
                'total_investment_amount': str(investment_amount),
                'monthly_amount': str(amount),
                'customer_name': customer_name
            }
        )

        # Create a Price for the Product (monthly recurring)
        price = stripe.Price.create(
            product=product.id,
            unit_amount=amount,
            currency=currency,
            recurring={
                'interval': 'month',
                'interval_count': 1  # Monthly
            }
        )

        return jsonify({
            'productId': product.id,
            'priceId': price.id
        })

    except stripe.error.StripeError as e:
        return jsonify({
            'error': str(e)
        }), 403
    except Exception as e:
        return jsonify({
            'error': 'An unexpected error occurred'
        }), 500

@payments_bp.route('/create-subscription', methods=['POST'])
def create_subscription():
    try:
        data = request.get_json()
        
        # Validate input
        price_id = data.get('priceId')
        customer_name = data.get('customerName', '')
        payment_method_type = data.get('paymentMethodType', 'card')
        payment_method_id = data.get('paymentMethodID')
        print('paymentID ',payment_method_id)
        
        if not price_id:
            return jsonify({'error': 'Price ID is required'}), 400

        # Retrieve the associated price to get product details
        price = stripe.Price.retrieve(price_id)
        product = stripe.Product.retrieve(price.product)
        print('priceID retrived',price_id)

        # Create a Customer
        customer = stripe.Customer.create(
            name=customer_name,
            metadata={
                'total_investment_amount': product.metadata.get('total_investment_amount', ''),
                'monthly_amount': product.metadata.get('monthly_amount', '')
            },
            payment_method = payment_method_id
        )
        stripe.Customer.modify(
            customer.id,
            invoice_settings = {'default_payment_method': payment_method_id}
        )
        print('customer created',customer.id)

        # Create a Subscription
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{
                'price': price_id,
            }],
            payment_settings={
                'payment_method_types': [payment_method_type],
                'save_default_payment_method': 'on_subscription'
            },
            metadata={
                'product_id': product.id,
                'total_investment_amount': product.metadata.get('total_investment_amount', ''),
                'monthly_amount': product.metadata.get('monthly_amount', '')
            },
        )
        print('sub created') # Create a payment method and attach it to the customer

        # Create a PaymentIntent for the first payment confirmation
        payment_intent = stripe.PaymentIntent.create(
            amount=int(product.metadata.get('monthly_amount', 0)),
            currency='sgd',
            customer=customer.id,
            payment_method_types=['card'],
            metadata={
                'subscription_id': subscription.id,
                'is_first_installment': 'true'
            }
        )
        print('intent created')

        return jsonify({
            'subscriptionId': subscription.id,
            'clientSecret': payment_intent.client_secret,
            'customerId': customer.id
        })

    except stripe.error.StripeError as e:
        return jsonify({
            'error': str(e)
        }), 403
    except Exception as e:
        return jsonify({
            'error': 'An unexpected error occurred'
        }), 500

@payments_bp.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    try:
        data = request.get_json()
        
        # Validate input
        amount = data.get('amount')
        currency = data.get('currency', 'sgd')
        
        if not amount:
            return jsonify({'error': 'Amount is required'}), 400

        # Metadata for installment tracking
        metadata = data.get('metadata', {})
        
        # Create a PaymentIntent
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,  # amount in cents
            currency=currency,
            payment_method_types=['card'],
            metadata=metadata
        )

        return jsonify({
            'clientSecret': payment_intent.client_secret
        })

    except stripe.error.StripeError as e:
        return jsonify({
            'error': str(e)
        }), 403
    except Exception as e:
        return jsonify({
            'error': 'An unexpected error occurred'
        }), 500
    
# Enhanced webhook for handling various payment events
@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400

    # Handle specific event types
    if event.type == 'payment_intent.succeeded':
        payment_intent = event.data.object
        metadata = payment_intent.metadata

        # Log or process installment details
        if metadata.get('is_first_installment') == 'true':
            print(f"First installment payment received: {metadata}")
            # Additional logic for first installment tracking

    elif event.type == 'invoice.paid':
        invoice = event.data.object
        subscription_id = invoice.subscription

        # Log successful monthly payment
        print(f"Invoice paid for subscription: {subscription_id}")
        # You could trigger additional logic here, like:
        # - Recording the payment
        # - Updating user's investment status

    elif event.type == 'subscription_schedule.completed':
        subscription_schedule = event.data.object
        print(f"Subscription schedule completed: {subscription_schedule.id}")
        # Handle end of 12-month subscription

    return 'Success', 200

@payments_bp.route('/payment-receipt', methods=['GET'])
# GET /payment-receipt?customer_id=cus_AbCdEf123456
def get_payment_receipt():
    try:
        # Get customer ID or subscription ID from query parameters
        customer_id = request.args.get('customer_id')
        subscription_id = request.args.get('subscription_id')
        
        if not customer_id and not subscription_id:
            return jsonify({'error': 'Either customer_id or subscription_id is required'}), 400
        
        payment_data = {}
        summary = {
            'total_paid': 0,
            'total_investment_amount': 0,
            'remaining_amount': 0,
            'currency': 'sgd',
            'payment_count': 0
        }
        
        # If subscription ID is provided, get customer from subscription
        if subscription_id and not customer_id:
            subscription = stripe.Subscription.retrieve(subscription_id)
            customer_id = subscription.customer
            
            # Get subscription metadata
            summary['total_investment_amount'] = int(subscription.metadata.get('total_investment_amount', 0))
        
        # Get payment history
        if customer_id:
            # Retrieve the customer to get metadata
            customer = stripe.Customer.retrieve(customer_id)
            if not summary['total_investment_amount']:
                summary['total_investment_amount'] = int(customer.metadata.get('total_investment_amount', 0))
            
            # Get all payments for this customer
            payment_intents = stripe.PaymentIntent.list(
                customer=customer_id,
                limit=100  # Adjust as needed
            )
            
            # Get all invoices for this customer
            invoices = stripe.Invoice.list(
                customer=customer_id,
                limit=100,  # Adjust as needed
                status='paid'
            )
            
            # Process payment intents
            payments = []
            for intent in payment_intents.data:
                if intent.status == 'succeeded':
                    payment = {
                        'payment_id': intent.id,
                        'amount': intent.amount,
                        'currency': intent.currency,
                        'date': intent.created,
                        'type': 'payment_intent',
                        'description': 'One-time payment' if not intent.metadata.get('subscription_id') 
                                      else 'Subscription payment'
                    }
                    
                    # Add first installment flag if applicable
                    if intent.metadata.get('is_first_installment') == 'true':
                        payment['description'] = 'First installment payment'
                    
                    payments.append(payment)
                    summary['total_paid'] += intent.amount
                    summary['payment_count'] += 1
            
            # Process invoices (for recurring subscription payments)
            for invoice in invoices.data:
                if not any(p['payment_id'] == invoice.payment_intent for p in payments if p['payment_id']):
                    payment = {
                        'payment_id': invoice.payment_intent,
                        'invoice_id': invoice.id,
                        'amount': invoice.amount_paid,
                        'currency': invoice.currency,
                        'date': invoice.created,
                        'period_start': invoice.period_start,
                        'period_end': invoice.period_end,
                        'type': 'invoice',
                        'description': f'Monthly installment ({invoice.number})'
                    }
                    
                    payments.append(payment)
                    summary['total_paid'] += invoice.amount_paid
                    summary['payment_count'] += 1
            
            # Sort payments by date
            payments.sort(key=lambda x: x['date'], reverse=True)
            
            # Calculate remaining amount
            if summary['total_investment_amount'] > 0:
                summary['remaining_amount'] = summary['total_investment_amount'] - summary['total_paid']
                if summary['remaining_amount'] < 0:
                    summary['remaining_amount'] = 0
            
            # Compile payment data
            payment_data = {
                'customer_id': customer_id,
                'customer_name': customer.name,
                'subscription_id': subscription_id if subscription_id else None,
                'summary': summary,
                'payments': payments
            }
            
            return jsonify(payment_data)
        
        return jsonify({'error': 'Customer not found'}), 404
        
    except stripe.error.StripeError as e:
        return jsonify({
            'error': str(e)
        }), 403
    except Exception as e:
        print(f"Error retrieving payment receipt: {str(e)}")
        return jsonify({
            'error': 'An unexpected error occurred'
        }), 500

@payments_bp.route('/download-receipt/<payment_id>', methods=['GET'])
#GET /download-receipt/pi_3NxYZ123456789
def download_receipt(payment_id):
    try:
        # Validate payment ID
        if not payment_id:
            return jsonify({'error': 'Payment ID is required'}), 400
            
        # Determine if this is a PaymentIntent or Invoice
        try:
            payment = stripe.PaymentIntent.retrieve(payment_id)
            payment_type = 'payment_intent'
        except stripe.error.StripeError:
            # Try as invoice payment
            invoices = stripe.Invoice.list(payment_intent=payment_id)
            if invoices and invoices.data:
                payment = invoices.data[0]
                payment_type = 'invoice'
            else:
                return jsonify({'error': 'Payment not found'}), 404
        
        # Get customer details
        customer_id = payment.customer if payment_type == 'payment_intent' else payment.customer
        customer = stripe.Customer.retrieve(customer_id)
        
        # Format receipt data
        receipt_data = {
            'receipt_id': f"RCPT-{payment_id[-8:]}",
            'payment_id': payment_id,
            'customer_name': customer.name,
            'customer_id': customer_id,
            'payment_date': payment.created if payment_type == 'payment_intent' else payment.created,
            'amount': payment.amount if payment_type == 'payment_intent' else payment.amount_paid,
            'currency': payment.currency,
            'status': 'Paid',
            'description': 'Investment Installment Payment',
            'payment_method_details': payment.charges.data[0].payment_method_details if payment_type == 'payment_intent' else None
        }
        
        # For subscription payments, add subscription details
        if payment_type == 'payment_intent' and payment.metadata.get('subscription_id'):
            try:
                subscription = stripe.Subscription.retrieve(payment.metadata.get('subscription_id'))
                receipt_data['subscription_id'] = subscription.id
                receipt_data['plan_details'] = {
                    'total_investment': subscription.metadata.get('total_investment_amount'),
                    'monthly_amount': subscription.metadata.get('monthly_amount')
                }
            except stripe.error.StripeError:
                # Subscription may have been deleted
                pass
        
        return jsonify(receipt_data)
        
    except stripe.error.StripeError as e:
        return jsonify({
            'error': str(e)
        }), 403
    except Exception as e:
        return jsonify({
            'error': 'An unexpected error occurred'
        }), 500