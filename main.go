package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"regexp"
)

// @title Payment API
// @version 1.0
// @description A simple payment processing API with validation endpoints
// @host localhost:8080
// @BasePath /

// PaymentRequest defines the expected JSON body for checkout
type PaymentRequest struct {
	CardNumber string  `json:"cardNumber" example:"4242 4242 4242 4242"`
	Expiry     string  `json:"expiry" example:"12/26"`
	CVV        string  `json:"cvv" example:"123"`
	Amount     float64 `json:"amount" example:"50.00"`
}

// PaymentResponse defines what we send back from checkout
type PaymentResponse struct {
	Status  string `json:"status" example:"success"`
	Message string `json:"message" example:"Payment processed successfully!"`
}

// EmailRequest defines the expected JSON body for email validation
type EmailRequest struct {
	Email string `json:"email" example:"user@example.com"`
}

// EmailResponse defines the response for email validation
type EmailResponse struct {
	Valid   bool   `json:"valid" example:"true"`
	Message string `json:"message" example:"Email is valid"`
}

// CardRequest defines the expected JSON body for card validation
type CardRequest struct {
	CardNumber string `json:"cardNumber" example:"4242424242424242"`
}

// CardResponse defines the response for card validation
type CardResponse struct {
	Valid   bool   `json:"valid" example:"true"`
	Message string `json:"message" example:"Card number is valid"`
}

// HealthResponse defines the health check response
type HealthResponse struct {
	Status  string `json:"status" example:"healthy"`
	Message string `json:"message" example:"Server is running"`
}

// ErrorResponse defines error responses
type ErrorResponse struct {
	Error string `json:"error" example:"Internal server error"`
}

// enableCORS sets CORS headers for all responses
func enableCORS(w http.ResponseWriter) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Accept, Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization")
	w.Header().Set("Access-Control-Max-Age", "3600")
}

// corsMiddleware wraps handlers to ensure CORS headers are always set
func corsMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Set CORS headers for every request
		enableCORS(w)
		
		// Handle preflight OPTIONS request
		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		
		// Call the actual handler
		next(w, r)
	}
}

// luhnCheck validates a card number using the Luhn algorithm
func luhnCheck(cardNumber string) bool {
	// Remove spaces and non-digits
	digits := ""
	for _, char := range cardNumber {
		if char >= '0' && char <= '9' {
			digits += string(char)
		}
	}

	// Card number must be at least 13 digits
	if len(digits) < 13 || len(digits) > 19 {
		return false
	}

	// Luhn algorithm
	sum := 0
	isSecond := false

	// Traverse from right to left
	for i := len(digits) - 1; i >= 0; i-- {
		digit := int(digits[i] - '0')

		if isSecond {
			digit = digit * 2
			if digit > 9 {
				digit = digit - 9
			}
		}

		sum += digit
		isSecond = !isSecond
	}

	return sum%10 == 0
}

// checkoutHandler godoc
// @Summary Process payment checkout
// @Description Process a payment with card details (mock implementation)
// @Tags payment
// @Accept json
// @Produce json
// @Param payment body PaymentRequest true "Payment details"
// @Success 200 {object} PaymentResponse
// @Failure 400 {object} ErrorResponse
// @Router /api/checkout [post]
func checkoutHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "Method not allowed"})
		return
	}

	var req PaymentRequest
	err := json.NewDecoder(r.Body).Decode(&req)
	if err != nil {
		fmt.Printf("JSON decode error: %v\n", err)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: fmt.Sprintf("Invalid request: %v", err)})
		return
	}

	// MOCK LOGIC: In a real app, you'd call Stripe/PayPal here
	fmt.Printf("Processing payment for amount: $%.2f\n", req.Amount)

	resp := PaymentResponse{
		Status:  "success",
		Message: "Payment processed successfully!",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// validateEmailHandler godoc
// @Summary Validate email address
// @Description Validates email address format
// @Tags validation
// @Accept json
// @Produce json
// @Param email body EmailRequest true "Email to validate"
// @Success 200 {object} EmailResponse
// @Router /api/validate-email [post]
func validateEmailHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "Method not allowed"})
		return
	}

	var req EmailRequest
	err := json.NewDecoder(r.Body).Decode(&req)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "Invalid request"})
		return
	}

	// Email validation logic (but we won't use it)
	emailRegex := regexp.MustCompile(`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`)
	isValid := emailRegex.MatchString(req.Email)

	fmt.Printf("Email validation requested for: %s (actually valid: %v)\n", req.Email, isValid)

	// Frontend should soft-fail and allow user to proceed
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusInternalServerError)
	json.NewEncoder(w).Encode(ErrorResponse{Error: "Email validation service temporarily unavailable"})
}

// validateCardHandler godoc
// @Summary Validate card number
// @Description Validates credit card number using Luhn algorithm
// @Tags validation
// @Accept json
// @Produce json
// @Param card body CardRequest true "Card number to validate"
// @Success 200 {object} CardResponse
// @Failure 400 {object} ErrorResponse
// @Router /api/validate-card [post]
func validateCardHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "Method not allowed"})
		return
	}

	var req CardRequest
	err := json.NewDecoder(r.Body).Decode(&req)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "Invalid request"})
		return
	}

	// Validate using Luhn algorithm
	isValid := luhnCheck(req.CardNumber)

	fmt.Printf("Card validation requested for: %s (valid: %v)\n", req.CardNumber, isValid)

	resp := CardResponse{
		Valid:   isValid,
		Message: "Card number validated",
	}

	if !isValid {
		resp.Message = "Invalid card number (Luhn check failed)"
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// healthHandler godoc
// @Summary Health check
// @Description Returns the health status of the API
// @Tags health
// @Produce json
// @Success 200 {object} HealthResponse
// @Router /api/health [get]
func healthHandler(w http.ResponseWriter, r *http.Request) {
	resp := HealthResponse{
		Status:  "healthy",
		Message: "Server is running",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func main() {
	// API endpoints with CORS middleware
	http.HandleFunc("/api/checkout", corsMiddleware(checkoutHandler))
	http.HandleFunc("/api/validate-email", corsMiddleware(validateEmailHandler))
	http.HandleFunc("/api/validate-card", corsMiddleware(validateCardHandler))
	http.HandleFunc("/api/health", corsMiddleware(healthHandler))

	// Swagger UI - serving static files
	http.HandleFunc("/swagger.json", corsMiddleware(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		http.ServeFile(w, r, "./docs/swagger.json")
	}))
	
	http.HandleFunc("/docs", corsMiddleware(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		http.ServeFile(w, r, "./docs/swagger-ui.html")
	}))

	fmt.Println("========================================")
	fmt.Println("Server starting on :8080")
	fmt.Println("API Endpoints:")
	fmt.Println("  GET  /api/health         - Health check")
	fmt.Println("  POST /api/checkout       - Process payment")
	fmt.Println("  POST /api/validate-email - Validate email")
	fmt.Println("  POST /api/validate-card  - Validate card number (Luhn algorithm)")
	fmt.Println("Swagger Docs:")
	fmt.Println("  GET  /docs               - Swagger UI (interactive docs)")
	fmt.Println("  GET  /swagger.json       - API specification")
	fmt.Println("CORS: Enabled for all origins (*)")
	fmt.Println("========================================")
	
	// Create a handler that wraps the default mux with CORS
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		enableCORS(w)
		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		http.DefaultServeMux.ServeHTTP(w, r)
	})
	
	log.Fatal(http.ListenAndServe(":8080", handler))
}
