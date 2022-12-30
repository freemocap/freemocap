import {createSlice, PayloadAction} from '@reduxjs/toolkit'

export class AppCameraState {

}

// const initialState: CounterState = {
//   value: 0,
// }

export const cameraSlice = createSlice({
  name: 'counter',
  initialState: new AppCameraState(),
  reducers: {
    increment: (state) => {
    },
    decrement: (state) => {
    },
    incrementByAmount: (state, action: PayloadAction<number>) => {
    },
  },
})

// Action creators are generated for each case reducer function
// export const { increment, decrement, incrementByAmount } = counterSlice.actions
//
// export default counterSlice.reducer
