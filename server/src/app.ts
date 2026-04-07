import express from 'express';
import cors from 'cors';

const app = express();

app.use(cors())

app.use(express.json())
app.use(express.urlencoded({extended: true}))
app.use(express.static('public'))

app.get('/api/health', (req, res)=>{
    res.status(200).json({status: 'ok'})
})


import soilRoute from "./routes/soil-route.js";
import farmlandRoute from "./routes/farmland-route.js";

app.use("/api/v1/soil", soilRoute);
app.use("/api/v1/farmland", farmlandRoute);

export default app;