class ApiError extends Error{
    statusCode: number;
    message: string;
    data: null;
    error?:any;
    stack?: string;
    success: boolean;

    constructor(
        statusCode: number,
        message: string,
        error?:any,
        stack?:string
    ){
        super(message)
        this.statusCode = statusCode;
        this.message = message
        this.data = null;
        this.success = false;

        if(error){
            this.error = error
        }
        if(stack){
            this.stack = stack
        }else{
            Error.captureStackTrace(this, this.constructor)
        }
    }
}

export{ ApiError }