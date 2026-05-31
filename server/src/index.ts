import "dotenv/config";
import app from "./app.js";
import { connectRedis } from "./configs/radis.js";

const PORT = process.env.PORT;

const listenServer = async () => {
  try {
    await connectRedis();
    app.listen(PORT, () => {
      console.log(`Server is running on port ${PORT}`);
    });
  } catch (error) {
    console.log(error);
  }
};
listenServer();